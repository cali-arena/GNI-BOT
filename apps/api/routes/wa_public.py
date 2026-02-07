"""
Public WhatsApp QR aliases under /wa/* for backward compatibility.
Same handlers and auth as /admin/wa/*. No weakening of security.
"""
from fastapi import APIRouter, Depends

from apps.api.routes.wa_bridge import (
    _do_reconnect,
    _fetch_qr,
    _fetch_status,
    require_wa_bridge_token,
)

# Same Bearer auth as /admin/wa/*. Clients expecting /wa/status, /wa/connect, /wa/qr
# get the same behavior. OpenAPI will show both /admin/wa/* and /wa/*.
wa_public_router = APIRouter(
    prefix="/wa",
    tags=["wa-public"],
    dependencies=[Depends(require_wa_bridge_token)],
)


@wa_public_router.get("/status")
async def wa_public_status() -> dict:
    """Alias for GET /admin/wa/status. Same handler, same auth."""
    return await _fetch_status()


@wa_public_router.post("/connect")
async def wa_public_connect() -> dict:
    """Alias for POST /admin/wa/reconnect. Triggers new QR generation."""
    return await _do_reconnect()


@wa_public_router.get("/qr")
async def wa_public_qr() -> dict:
    """Alias for GET /admin/wa/qr. Returns QR string or null."""
    return await _fetch_qr()
