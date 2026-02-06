"""
Per-user rate limiting for WhatsApp endpoints: Redis with in-memory fallback.
Keys: wa:connect:{user_id}, wa:qr:{user_id}, wa:status:{user_id}, wa:send:{user_id}.
Sliding window: count entries in window; if Redis unavailable use in-memory dict.
"""
import time
from collections import defaultdict
from typing import Optional

from apps.shared.secrets import get_secret

_redis: Optional[object] = None
_MEMORY: dict[str, list[float]] = defaultdict(list)


def _get_redis():
    global _redis
    if _redis is not None:
        return _redis
    try:
        import redis
        from apps.shared.config import REDIS_URL_DEFAULT
        url = get_secret("REDIS_URL", REDIS_URL_DEFAULT)
        if url and url.strip().startswith("redis://"):
            _redis = redis.Redis.from_url(url)
            _redis.ping()
            return _redis
    except Exception:
        pass
    _redis = False  # type: ignore[assignment]
    return None


def _memory_key(prefix: str, user_id: int, window: str) -> str:
    return f"{prefix}:{user_id}:{window}"


def _redis_key(prefix: str, user_id: int) -> str:
    return f"wa:{prefix}:{user_id}"


def _check_memory(prefix: str, user_id: int, window_seconds: float, limit: int) -> bool:
    key = _memory_key(prefix, user_id, str(window_seconds))
    now = time.monotonic()
    cutoff = now - window_seconds
    _MEMORY[key] = [t for t in _MEMORY[key] if t > cutoff]
    if len(_MEMORY[key]) >= limit:
        return False
    _MEMORY[key].append(now)
    return True


def _check_redis(prefix: str, user_id: int, window_seconds: int, limit: int) -> bool:
    r = _get_redis()
    if not r:
        return True  # no Redis => allow (fallback to memory in caller)
    key = _redis_key(prefix, user_id)
    try:
        pipe = r.pipeline()
        now = time.time()
        pipe.zadd(key, {str(now): now})
        pipe.zremrangebyscore(key, 0, now - window_seconds)
        pipe.zcard(key)
        pipe.expire(key, window_seconds + 60)
        _, _, count, _ = pipe.execute()
        if count and int(count) > limit:
            r.zrem(key, str(now))  # undo the add
            return False
        return True
    except Exception:
        return True  # on error allow (or could fallback to memory)


def check_wa_connect(user_id: int, limit: int = 5, window_seconds: int = 3600) -> bool:
    """Allow if under limit connect attempts per user per hour. Returns True if allowed."""
    if _get_redis():
        allowed = _check_redis("connect", user_id, window_seconds, limit)
        if not allowed:
            return False
        return True
    return _check_memory("connect", user_id, float(window_seconds), limit)


def check_wa_qr(user_id: int, limit: int = 30, window_seconds: int = 60) -> bool:
    """Allow if under limit QR fetches per user per minute."""
    if _get_redis():
        allowed = _check_redis("qr", user_id, window_seconds, limit)
        if not allowed:
            return False
        return True
    return _check_memory("qr", user_id, float(window_seconds), limit)


def check_wa_status(user_id: int, limit: int = 60, window_seconds: int = 60) -> bool:
    """Allow if under limit status fetches per user per minute."""
    if _get_redis():
        allowed = _check_redis("status", user_id, window_seconds, limit)
        if not allowed:
            return False
        return True
    return _check_memory("status", user_id, float(window_seconds), limit)


def check_wa_send(user_id: int, limit: int = 10, window_seconds: int = 60) -> bool:
    """Allow if under limit send-group per user per minute."""
    if _get_redis():
        allowed = _check_redis("send", user_id, window_seconds, limit)
        if not allowed:
            return False
        return True
    return _check_memory("send", user_id, float(window_seconds), limit)
