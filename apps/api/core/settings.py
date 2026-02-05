"""
API env config via Pydantic Settings. Treats empty string as missing -> use default.
Used at startup; validators ensure ints never get raw empty strings.
"""
from __future__ import annotations

from typing import Optional

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from apps.shared.config import DATABASE_URL_DEFAULT, REDIS_URL_DEFAULT
from apps.shared.env_helpers import parse_int_default
from apps.shared.secrets import get_secret


def _get(key: str, default: str = "") -> str:
    """Env lookup: empty string is treated as missing (get_secret already does this)."""
    return get_secret(key, default) or ""


class ApiSettings(BaseSettings):
    """API configuration from env. Empty values fall back to defaults."""

    model_config = SettingsConfigDict(extra="ignore")

    DATABASE_URL: str = DATABASE_URL_DEFAULT
    REDIS_URL: str = REDIS_URL_DEFAULT
    JWT_SECRET: str = ""
    JWT_EXPIRY_SECONDS: int = 86400  # 24h
    API_KEY: str = ""

    @field_validator("JWT_EXPIRY_SECONDS", mode="before")
    @classmethod
    def _coerce_jwt_expiry(cls, v: object) -> int:
        if v is None:
            return 86400
        if isinstance(v, int):
            return max(1, min(v, 604800)) if v else 86400
        s = (v or "").strip()
        if not s:
            return 86400
        try:
            n = int(s)
            return max(1, min(n, 604800)) if n else 86400
        except ValueError:
            return 86400

    @classmethod
    def from_env(cls) -> "ApiSettings":
        """Build from current env (get_secret for compatibility with secrets provider)."""
        return cls(
            DATABASE_URL=_get("DATABASE_URL", DATABASE_URL_DEFAULT),
            REDIS_URL=_get("REDIS_URL", REDIS_URL_DEFAULT),
            JWT_SECRET=_get("JWT_SECRET"),
            JWT_EXPIRY_SECONDS=parse_int_default(_get("JWT_EXPIRY_SECONDS", "86400"), 86400, 1, 604800),
            API_KEY=_get("API_KEY") or _get("ADMIN_API_KEY"),
        )


_settings: Optional[ApiSettings] = None


def get_api_settings() -> ApiSettings:
    """Return cached API settings. Call once at startup after env is loaded."""
    global _settings
    if _settings is None:
        _settings = ApiSettings.from_env()
    return _settings
