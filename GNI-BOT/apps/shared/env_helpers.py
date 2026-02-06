"""Shared helpers for env parsing: treat empty as missing, safe int parsing."""
import os
from typing import Optional


def env_int(
    name: str,
    default: int,
    *,
    min_value: Optional[int] = None,
    max_value: Optional[int] = None,
) -> int:
    """Read integer from env; missing or empty/whitespace -> default. Enforce min/max if provided."""
    raw = os.environ.get(name, "")
    s = (raw or "").strip()
    if not s:
        return default
    try:
        n = int(s)
    except ValueError:
        raise ValueError(f"Invalid integer for {name!r}: {s!r}")
    if min_value is not None and n < min_value:
        raise ValueError(f"{name!r} must be >= {min_value}, got {n}")
    if max_value is not None and n > max_value:
        raise ValueError(f"{name!r} must be <= {max_value}, got {n}")
    return n


def env_float(
    name: str,
    default: float,
    *,
    min_value: Optional[float] = None,
    max_value: Optional[float] = None,
) -> float:
    """Read float from env; missing or empty/whitespace -> default. Enforce min/max if provided."""
    raw = os.environ.get(name, "")
    s = (raw or "").strip()
    if not s:
        return default
    try:
        n = float(s)
    except ValueError:
        raise ValueError(f"Invalid float for {name!r}: {s!r}")
    if min_value is not None and n < min_value:
        raise ValueError(f"{name!r} must be >= {min_value}, got {n}")
    if max_value is not None and n > max_value:
        raise ValueError(f"{name!r} must be <= {max_value}, got {n}")
    return n
