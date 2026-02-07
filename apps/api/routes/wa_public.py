"""
Public WhatsApp QR endpoints under /wa/* for UI access (X-API-Key auth).
Uses same underlying logic as /admin/wa/* but auth is X-API-Key (or JWT), not Bearer bridge token.
Bridge token stays server-side; client sends X-API-Key.
"""
from fastapi import APIRouter, Depends

from apps.api.auth import require_auth
from apps.api.routes.wa_bridge import (
    _do_reconnect,
    _fetch_qr,
    _fetch_status,
)

wa_public_router = APIRouter(
    prefix="/wa",
    tags=["wa-public"],
    dependencies=[Depends(require_auth)],
)


@wa_public_router.get(
    "/status",
    summary="WhatsApp connection status",
    description="Returns connected, status, lastDisconnectReason, server_time. Use X-API-Key header.",
)
async def wa_public_status() -> dict:
    """GET /wa/status — proxy to whatsapp-bot health. Auth: X-API-Key or Bearer JWT."""
    return await _fetch_status()


@wa_public_router.post(
    "/connect",
    summary="Trigger WhatsApp reconnect",
    description="Triggers bot to logout and reconnect, generating a new QR. Use X-API-Key header.",
)
async def wa_public_connect() -> dict:
    """POST /wa/connect — trigger new QR generation. Auth: X-API-Key or Bearer JWT."""
    return await _do_reconnect()


@wa_public_router.get(
    "/qr",
    summary="Get WhatsApp QR code",
    description="Returns qr (string or null), status, expires_in, server_time. Use X-API-Key header.",
)
async def wa_public_qr() -> dict:
    """GET /wa/qr — returns QR string or null. Auth: X-API-Key or Bearer JWT."""
    return await _fetch_qr()
