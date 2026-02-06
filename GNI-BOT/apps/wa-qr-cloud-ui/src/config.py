"""
Config: optional API base URL from env. No required secrets; app never blocks.
API_BASE_URL from GNI_API_BASE_URL; can be overridden in UI via session_state["api_base_url"].
"""
import os
from typing import Any

# Optional; empty is OK - app will show "paste URL" input. Never block startup.
API_BASE_URL = os.getenv("GNI_API_BASE_URL", "").strip().rstrip("/")


def get_config() -> dict[str, Any]:
    """Return config dict. No required keys; no validation."""
    return {"API_BASE_URL": API_BASE_URL}


def validate_config() -> None:
    """No-op. No mandatory validation; app never blocked by config."""
    pass
