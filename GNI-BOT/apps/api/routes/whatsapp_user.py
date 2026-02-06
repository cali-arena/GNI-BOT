"""
Per-user WhatsApp endpoints. All require JWT (get_current_user).
Calls internal whatsapp-bot (http://whatsapp-bot:3100); never expose bot publicly.
Rate limits: Redis with in-memory fallback. Structured logs (user_id only; never QR).
QR expiry enforced: treat expired QR as null.
"""
import logging
import time
from datetime import datetime, timezone
from typing import Any, Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from auth import get_current_user
from db import get_db_dependency
from db.models import EventsLog, User, WhatsAppSession
from schemas import SendGroupIn

from wa_rate_limit import check_wa_connect, check_wa_qr, check_wa_send, check_wa_status
from apps.shared.config import WHATSAPP_BOT_BASE_URL_DEFAULT
from apps.shared.secrets import get_secret

logger = logging.getLogger(__name__)

WA_BOT_BASE_URL = get_secret("WA_BOT_BASE_URL", WHATSAPP_BOT_BASE_URL_DEFAULT).rstrip("/")
WA_BOT_TIMEOUT = float(get_secret("WA_BOT_TIMEOUT_SECONDS", "10"))
WA_QR_TTL_SECONDS = int(get_secret("WA_QR_TTL_SECONDS", "60"))
RATE_CONNECT_PER_HOUR = int(get_secret("WA_CONNECT_RATE_PER_HOUR", "5"))
RATE_QR_PER_MINUTE = int(get_secret("WA_QR_RATE_PER_MINUTE", "30"))
RATE_STATUS_PER_MINUTE = int(get_secret("WA_STATUS_RATE_PER_MINUTE", "60"))
RATE_SEND_GROUP_PER_MINUTE = int(get_secret("WA_SEND_GROUP_RATE_PER_MINUTE", "10"))
MAX_TEXT_LENGTH = int(get_secret("WA_SEND_MAX_TEXT_LENGTH", "4096"))
CHUNK_SIZE = int(get_secret("WA_SEND_CHUNK_SIZE", "4000"))


def _log_wa(action: str, user_id: int, **extra: Any) -> None:
    """Structured log for WhatsApp actions. Never include QR or secrets."""
    try:
        import structlog
        structlog.get_logger().info("wa_action", action=action, user_id=user_id, **extra)
    except ImportError:
        logger.info("wa_action action=%s user_id=%s %s", action, user_id, extra)


def _get_or_create_session(session: Session, user_id: int) -> WhatsAppSession:
    row = session.query(WhatsAppSession).filter(WhatsAppSession.user_id == user_id).first()
    if row:
        return row
    row = WhatsAppSession(user_id=user_id, status="disconnected")
    session.add(row)
    session.flush()
    return row


async def _bot_post(path: str, json_body: Optional[dict] = None) -> tuple[Optional[dict], Optional[str]]:
    url = f"{WA_BOT_BASE_URL}{path}"
    try:
        async with httpx.AsyncClient(timeout=WA_BOT_TIMEOUT) as client:
            r = await client.post(url, json=json_body or {})
            r.raise_for_status()
            return (r.json() if r.content else None), None
    except httpx.TimeoutException:
        return None, "whatsapp-bot timeout"
    except httpx.HTTPStatusError as e:
        try:
            detail = e.response.json().get("detail", e.response.text[:200])
        except Exception:
            detail = str(e)[:200]
        return None, detail
    except Exception as e:
        logger.warning("whatsapp_user: bot post %s error: %s", path, type(e).__name__)
        return None, "whatsapp-bot unreachable"


async def _bot_get(path: str, params: Optional[dict] = None) -> tuple[Optional[dict], Optional[str]]:
    url = f"{WA_BOT_BASE_URL}{path}"
    try:
        async with httpx.AsyncClient(timeout=WA_BOT_TIMEOUT) as client:
            r = await client.get(url, params=params or {})
            r.raise_for_status()
            return (r.json() if r.content else None), None
    except httpx.TimeoutException:
        return None, "whatsapp-bot timeout"
    except httpx.HTTPStatusError as e:
        try:
            detail = e.response.json().get("detail", e.response.text[:200])
        except Exception:
            detail = str(e)[:200]
        return None, detail
    except Exception as e:
        logger.warning("whatsapp_user: bot get %s error: %s", path, type(e).__name__)
        return None, "whatsapp-bot unreachable"


router = APIRouter(prefix="/whatsapp", tags=["whatsapp-user"])


@router.post("/connect")
async def whatsapp_connect(
    user: User = Depends(get_current_user),
    session: Session = Depends(get_db_dependency),
) -> dict[str, str]:
    """
    Ensure whatsapp_sessions row exists, call whatsapp-bot POST /session/start {user_id},
    update session_path and status=qr_ready. Rate limit 5/hour per user.
    """
    if not check_wa_connect(user.id, limit=RATE_CONNECT_PER_HOUR, window_seconds=3600):
        _log_wa("connect_rate_limited", user.id)
        raise HTTPException(status_code=429, detail="Connect rate limit exceeded (5/hour per user)")

    row = _get_or_create_session(session, user.id)
    data, err = await _bot_post("/session/start", {"user_id": user.id})
    if err:
        _log_wa("connect_error", user.id, error=err)
        raise HTTPException(status_code=502, detail=err or "whatsapp-bot error")

    session_path = (data or {}).get("session_path") if isinstance(data, dict) else None
    if session_path:
        row.session_path = session_path
    else:
        row.session_path = row.session_path or f"/data/wa_sessions/user_{user.id}/"
    row.status = "qr_ready"
    session.flush()
    session.commit()
    _log_wa("connect_ok", user.id, status="qr_ready")
    return {"status": "qr_ready"}


def _qr_expired(data: dict, ttl_seconds: int) -> bool:
    """True if QR has qr_expires_at in the past; treat as expired (return null)."""
    if not data:
        return True
    exp = data.get("qr_expires_at") or data.get("expires_at")
    if exp is None:
        return False
    try:
        if isinstance(exp, (int, float)):
            return time.time() > float(exp)
        if isinstance(exp, str):
            from datetime import datetime as dt
            ts = dt.fromisoformat(exp.replace("Z", "+00:00")).timestamp()
            return time.time() > ts
    except Exception:
        pass
    return False


@router.get("/qr")
async def whatsapp_qr(
    user: User = Depends(get_current_user),
    session: Session = Depends(get_db_dependency),
) -> dict[str, Any]:
    """
    Get QR for current user. Rate limit 30/min per user. Never log qr content.
    Expired QR (by qr_expires_at) is returned as null.
    """
    if not check_wa_qr(user.id, limit=RATE_QR_PER_MINUTE, window_seconds=60):
        _log_wa("qr_rate_limited", user.id)
        raise HTTPException(status_code=429, detail="QR rate limit exceeded (30/min per user)")

    data, err = await _bot_get("/session/qr", {"user_id": user.id})
    if err:
        _log_wa("qr_error", user.id, error=err)
        raise HTTPException(status_code=502, detail=err or "whatsapp-bot error")

    data = data if isinstance(data, dict) else {}
    qr = data.get("qr")
    if qr and _qr_expired(data, WA_QR_TTL_SECONDS):
        qr = None
    status = data.get("status", "unknown")
    expires_in = WA_QR_TTL_SECONDS if qr else 0
    _log_wa("qr_fetch", user.id, has_qr=bool(qr), status=status)
    return {"qr": qr, "expires_in": expires_in, "status": status}


@router.get("/status")
async def whatsapp_status(
    user: User = Depends(get_current_user),
    session: Session = Depends(get_db_dependency),
) -> dict[str, Any]:
    """
    Get session status for current user. Sync phone_e164/connected_at to DB if connected.
    Rate limit 60/min per user.
    """
    if not check_wa_status(user.id, limit=RATE_STATUS_PER_MINUTE, window_seconds=60):
        _log_wa("status_rate_limited", user.id)
        raise HTTPException(status_code=429, detail="Status rate limit exceeded (60/min per user)")

    data, err = await _bot_get("/session/status", {"user_id": user.id})
    if err:
        _log_wa("status_error", user.id, error=err)
        raise HTTPException(status_code=502, detail=err or "whatsapp-bot error")
    _log_wa("status_fetch", user.id, connected=data.get("connected") if isinstance(data, dict) else None)

    if not isinstance(data, dict):
        return {"status": "unknown", "phone": None, "connected_at": None, "lastDisconnectReason": None}

    status = data.get("status", "unknown")
    connected = data.get("connected", False)
    phone = data.get("phone") or data.get("phone_e164")
    last_reason = data.get("lastDisconnectReason")

    row = session.query(WhatsAppSession).filter(WhatsAppSession.user_id == user.id).first()
    if row:
        if connected and phone:
            row.phone_e164 = phone
            if not row.connected_at:
                row.connected_at = datetime.now(timezone.utc)
            row.status = "connected"
        else:
            row.status = "disconnected" if not connected else row.status
        try:
            session.commit()
        except Exception:
            session.rollback()

    return {
        "status": status,
        "connected": connected,
        "phone": phone,
        "connected_at": row.connected_at.isoformat() if row and row.connected_at else None,
        "lastDisconnectReason": last_reason,
    }


@router.post("/send-group")
async def whatsapp_send_group(
    body: SendGroupIn,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_db_dependency),
) -> dict[str, Any]:
    """
    Send text to a group using the current user's session. Rate limit 10/min per user.
    Validates text length; may split into chunks if configured.
    """
    if not check_wa_send(user.id, limit=RATE_SEND_GROUP_PER_MINUTE, window_seconds=60):
        _log_wa("send_rate_limited", user.id)
        raise HTTPException(status_code=429, detail="Send rate limit exceeded (10/min per user)")

    text = (body.text or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="text required")
    if len(text) > MAX_TEXT_LENGTH:
        raise HTTPException(status_code=400, detail=f"text exceeds max length ({MAX_TEXT_LENGTH})")

    group_id = (body.group_id or "").strip()
    if not group_id:
        raise HTTPException(status_code=400, detail="group_id required")

    # Optional: split into chunks if text is very long
    chunks = []
    if len(text) <= CHUNK_SIZE:
        chunks = [text]
    else:
        for i in range(0, len(text), CHUNK_SIZE):
            chunks.append(text[i : i + CHUNK_SIZE])

    results = []
    for chunk in chunks:
        payload = {"user_id": user.id, "group_id": group_id, "text": chunk}
        data, err = await _bot_post("/session/send-group", payload)
        if err:
            _log_wa("send_error", user.id, group_id=group_id, error=err)
            raise HTTPException(status_code=502, detail=err or "whatsapp-bot error")
        results.append(data)

    _log_wa("send_ok", user.id, group_id=group_id, chunks=len(chunks))

    # Optional: log event per user
    try:
        log = EventsLog(
            event_type="whatsapp_send_group",
            payload={"user_id": user.id, "group_id": group_id, "chunks": len(chunks)},
        )
        session.add(log)
        session.commit()
    except Exception:
        session.rollback()

    return {"sent": True, "chunks": len(chunks)}
