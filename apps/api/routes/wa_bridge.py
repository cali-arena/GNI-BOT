"""
Secure WhatsApp QR Bridge: proxy status and QR from internal whatsapp-bot to a remote UI
(Streamlit Cloud) without exposing the bot service. All endpoints require Bearer token.

Routes:
  /admin/wa/* — admin routes (primary)
  /wa/*       — public aliases (same auth) for backward compatibility with clients
                expecting /wa/status, /wa/connect, /wa/qr
"""
import logging
import time
from collections import defaultdict
from datetime import datetime, timezone
from typing import Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from apps.shared.config import WHATSAPP_BOT_BASE_URL_DEFAULT
from apps.shared.secrets import get_secret

logger = logging.getLogger(__name__)

WA_BOT_BASE_URL = get_secret("WA_BOT_BASE_URL", WHATSAPP_BOT_BASE_URL_DEFAULT).rstrip("/")
WA_QR_BRIDGE_TOKEN = get_secret("WA_QR_BRIDGE_TOKEN", "").strip()
WA_QR_TTL_SECONDS = int(get_secret("WA_QR_TTL_SECONDS", "120"))
WA_QR_RATE_LIMIT_PER_MINUTE = int(get_secret("WA_QR_RATE_LIMIT_PER_MINUTE", "90"))
WA_BOT_TIMEOUT_SECONDS = 5.0

http_bearer = HTTPBearer(auto_error=False)

# In-memory rate limit for /admin/wa/qr: IP -> list of request timestamps (last minute)
_qr_rate: dict[str, list[float]] = defaultdict(list)


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _prune_and_count(ip: str) -> int:
    now = time.monotonic()
    cutoff = now - 60.0
    _qr_rate[ip] = [t for t in _qr_rate[ip] if t > cutoff]
    return len(_qr_rate[ip])


async def require_wa_bridge_token(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(http_bearer),
) -> None:
    """Require Authorization: Bearer <WA_QR_BRIDGE_TOKEN>. 401 if missing or invalid."""
    if not WA_QR_BRIDGE_TOKEN:
        raise HTTPException(
            status_code=503,
            detail="WhatsApp QR Bridge is not configured (WA_QR_BRIDGE_TOKEN not set)",
        )
    if not credentials or not credentials.credentials:
        raise HTTPException(status_code=401, detail="Missing Authorization header")
    if credentials.credentials.strip() != WA_QR_BRIDGE_TOKEN:
        raise HTTPException(status_code=401, detail="Unauthorized")


# --- Shared handlers (no router path): used by both /admin/wa and /wa ---
# Security: both use same Bearer auth. No weakening of auth for /wa/*.


async def _fetch_status() -> dict:
    """Proxy to whatsapp-bot /health. Returns connected, status, lastDisconnectReason, server_time."""
    now = datetime.now(timezone.utc).isoformat()
    try:
        async with httpx.AsyncClient(timeout=WA_BOT_TIMEOUT_SECONDS) as client:
            r = await client.get(f"{WA_BOT_BASE_URL}/health")
            r.raise_for_status()
            data = r.json()
    except httpx.TimeoutException:
        logger.warning("wa_bridge: whatsapp-bot health timeout")
        return {
            "connected": False,
            "status": "timeout",
            "lastDisconnectReason": None,
            "server_time": now,
        }
    except Exception as e:
        logger.warning("wa_bridge: whatsapp-bot health error: %s", type(e).__name__)
        return {
            "connected": False,
            "status": "unreachable",
            "lastDisconnectReason": None,
            "server_time": now,
        }
    return {
        "connected": data.get("connected", False),
        "status": data.get("status", "unknown"),
        "lastDisconnectReason": data.get("lastDisconnectReason"),
        "server_time": now,
    }


def _fetch_qr_sync() -> dict:
    """
    Read Redis first; if miss, proxy to bot and cache on hit.
    Returns: { "qr": str|null, "status": "qr_ready"|"not_ready", "ts": unix_ts?, "expires_in", "server_time" }
    """
    import time
    from apps.api.wa_qr_cache import get_cached_qr, set_cached_qr

    now = datetime.now(timezone.utc).isoformat()
    now_ts = time.time()

    # 1) Check Redis first
    cached = get_cached_qr()
    if cached:
        qr_str, ts = cached
        return {
            "qr": qr_str,
            "status": "qr_ready",
            "ts": int(ts),
            "expires_in": WA_QR_TTL_SECONDS,
            "server_time": now,
        }

    # 2) Proxy to bot
    try:
        import httpx
        with httpx.Client(timeout=WA_BOT_TIMEOUT_SECONDS) as client:
            r = client.get(f"{WA_BOT_BASE_URL}/qr")
            r.raise_for_status()
            data = r.json()
    except Exception as e:
        logger.warning("wa_bridge: whatsapp-bot qr error: %s", type(e).__name__)
        return {"qr": None, "status": "not_ready", "expires_in": 0, "server_time": now}

    qr = data.get("qr")
    if qr:
        set_cached_qr(qr, ttl=WA_QR_TTL_SECONDS)
        return {
            "qr": qr,
            "status": "qr_ready",
            "ts": int(now_ts),
            "expires_in": WA_QR_TTL_SECONDS,
            "server_time": now,
        }
    return {
        "qr": None,
        "status": "not_ready",
        "expires_in": 0,
        "server_time": now,
    }


async def _fetch_qr() -> dict:
    """Async wrapper: run sync _fetch_qr_sync in thread pool."""
    import asyncio
    return await asyncio.to_thread(_fetch_qr_sync)


async def _do_reconnect() -> dict:
    """Trigger whatsapp-bot to logout and reconnect, generating a new QR."""
    now = datetime.now(timezone.utc).isoformat()
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            r = await client.post(f"{WA_BOT_BASE_URL}/reconnect")
            r.raise_for_status()
            return r.json()
    except httpx.TimeoutException:
        logger.warning("wa_bridge: whatsapp-bot reconnect timeout")
        return {"ok": False, "error": "timeout", "server_time": now}
    except Exception as e:
        logger.warning("wa_bridge: whatsapp-bot reconnect error: %s", type(e).__name__)
        return {"ok": False, "error": str(e)[:100], "server_time": now}


# --- /admin/wa/* router (unchanged behavior) ---
router = APIRouter(prefix="/admin/wa", tags=["wa-bridge"], dependencies=[Depends(require_wa_bridge_token)])


@router.get("/status")
async def wa_status() -> dict:
    """Proxy to whatsapp-bot /health."""
    return await _fetch_status()


@router.get("/qr")
async def wa_qr() -> dict:
    """Proxy to whatsapp-bot /qr."""
    return await _fetch_qr()


@router.post("/reconnect")
async def wa_reconnect() -> dict:
    """Trigger whatsapp-bot reconnect."""
    return await _do_reconnect()
