"""
WhatsApp QR Redis cache: wa:last_qr, wa:last_qr_ts.
Bridge writes QR when received from bot; GET /wa/qr reads from cache first.
"""
import logging
import time
from typing import Optional

from apps.shared.config import REDIS_URL_DEFAULT
from apps.shared.secrets import get_secret

logger = logging.getLogger(__name__)

WA_QR_KEY = "wa:last_qr"
WA_QR_TS_KEY = "wa:last_qr_ts"
WA_QR_TTL = int(get_secret("WA_QR_TTL_SECONDS", "120"))


def _get_redis():
    """Lazy Redis client. Returns None if unavailable."""
    try:
        import redis
        url = get_secret("REDIS_URL", REDIS_URL_DEFAULT)
        if not url:
            return None
        return redis.Redis.from_url(url)
    except Exception as e:
        logger.debug("wa_qr_cache: redis unavailable: %s", e)
        return None


def get_cached_qr() -> Optional[tuple[str, float]]:
    """Return (qr_string, unix_ts) if cached, else None."""
    r = _get_redis()
    if not r:
        return None
    try:
        qr = r.get(WA_QR_KEY)
        ts_raw = r.get(WA_QR_TS_KEY)
        if qr is not None:
            qr_str = qr.decode("utf-8") if isinstance(qr, bytes) else str(qr)
            ts = float(ts_raw.decode("utf-8")) if ts_raw else time.time()
            return (qr_str, ts)
    except Exception as e:
        logger.warning("wa_qr_cache: get error: %s", e)
    return None


def set_cached_qr(qr: str, ttl: int = WA_QR_TTL) -> None:
    """Cache QR string with TTL. Writes wa:last_qr and wa:last_qr_ts."""
    if not qr:
        return
    r = _get_redis()
    if not r:
        return
    try:
        ts = time.time()
        pipe = r.pipeline()
        pipe.setex(WA_QR_KEY, ttl, qr)
        pipe.setex(WA_QR_TS_KEY, ttl, str(ts))
        pipe.execute()
    except Exception as e:
        logger.warning("wa_qr_cache: set error: %s", e)
