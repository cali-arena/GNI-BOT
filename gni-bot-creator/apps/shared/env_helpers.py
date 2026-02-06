"""Shared helpers for env parsing: treat empty as missing, safe int parsing."""


def parse_int_default(raw: str, default: int, min_val: int, max_val: int) -> int:
    """Parse int from string; empty or invalid -> default; clamp to [min_val, max_val]."""
    s = (raw or "").strip()
    if not s:
        return default
    try:
        n = int(s)
        return max(min_val, min(max_val, n)) if n else default
    except ValueError:
        return default
