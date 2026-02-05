"""
Central config: st.secrets first, then os.environ. No plaintext secrets in code.
Required for Cloud: GNI_API_BASE_URL only (login via POST /auth/login, JWT in session; no WA tokens).
Optional: SEED_CLIENT_* for legacy in-app fallback; API_KEY for monitoring/posts.
"""
import os
from typing import Any

import streamlit as st

# Only API base URL required; Streamlit talks to API over HTTPS, uses JWT (no WA_QR_BRIDGE_TOKEN)
REQUIRED_KEYS = ("GNI_API_BASE_URL",)
OPTIONAL_KEYS = (
    "SEED_CLIENT_EMAIL",
    "SEED_CLIENT_PASSWORD",
    "SEED_CLIENT_ROLE",
    "WA_QR_BRIDGE_TOKEN",
    "API_KEY",
    "ADMIN_API_KEY",
    "AUTO_REFRESH_SECONDS",
)


def _get(key: str, default: str = "") -> str:
    """Read from st.secrets first, then os.environ. Stripped string."""
    val = ""
    try:
        if hasattr(st, "secrets") and st.secrets is not None:
            val = st.secrets.get(key, "") or ""
    except (TypeError, KeyError, AttributeError):
        pass
    if not (val and str(val).strip()):
        val = os.environ.get(key, default) or ""
    return str(val).strip()


def get_config() -> dict[str, Any]:
    """Return full config dict. All keys from secrets/env."""
    base_url = _get("GNI_API_BASE_URL").rstrip("/")
    token = _get("WA_QR_BRIDGE_TOKEN")
    seed_email = _get("SEED_CLIENT_EMAIL")
    seed_password = _get("SEED_CLIENT_PASSWORD")
    seed_role = _get("SEED_CLIENT_ROLE") or "client"
    api_key = _get("API_KEY") or _get("ADMIN_API_KEY")
    try:
        auto_refresh = int(_get("AUTO_REFRESH_SECONDS") or "3")
    except ValueError:
        auto_refresh = 3
    return {
        "GNI_API_BASE_URL": base_url,
        "WA_QR_BRIDGE_TOKEN": token,
        "SEED_CLIENT_EMAIL": seed_email,
        "SEED_CLIENT_PASSWORD": seed_password,
        "SEED_CLIENT_ROLE": seed_role.strip().lower(),
        "API_KEY": api_key,
        "AUTO_REFRESH_SECONDS": auto_refresh,
    }


def has_seed_for_legacy() -> bool:
    """True if SEED_CLIENT_EMAIL and SEED_CLIENT_PASSWORD are set (legacy in-app login fallback)."""
    c = get_config()
    return bool((c.get("SEED_CLIENT_EMAIL") or "").strip() and (c.get("SEED_CLIENT_PASSWORD") or "").strip())


def validate_config() -> None:
    """
    Validate required keys. On failure: friendly banner with ✅/⚠️ emojis and st.stop().
    """
    cfg = get_config()
    missing = [k for k in REQUIRED_KEYS if not (cfg.get(k) or "").strip()]
    if not missing:
        return
    st.error(
        "⚠️ **Missing configuration**\n\n"
        "Set these in **Streamlit Cloud → Settings → Secrets** (or env):\n\n"
        + "\n".join(f"• **{k}**" for k in missing)
        + "\n\n"
        "✅ After saving secrets, refresh the app."
    )
    st.stop()
