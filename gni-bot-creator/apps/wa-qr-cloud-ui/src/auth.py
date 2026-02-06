"""
Auth: bcrypt, session-only (st.session_state). No file persistence (Cloud-safe).
Seed user from SEED_CLIENT_* in config; login/logout/require_login/require_role/current_user.
"""
from typing import Any, Optional

try:
    from passlib.hash import bcrypt as passlib_bcrypt
    _use_passlib = True
except ImportError:
    try:
        import bcrypt
        _use_passlib = False
    except ImportError:
        bcrypt = None
        passlib_bcrypt = None
        _use_passlib = False


# In-memory only (no disk). Seed user populated on startup.
_users: dict[str, dict[str, Any]] = {}


def _hash_password(plain: str) -> str:
    if _use_passlib and passlib_bcrypt:
        return passlib_bcrypt.hash(plain)
    if bcrypt:
        return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
    raise RuntimeError("Install passlib[bcrypt] or bcrypt")


def _verify_password(plain: str, hashed: str) -> bool:
    if not plain or not hashed:
        return False
    try:
        if _use_passlib and passlib_bcrypt:
            return passlib_bcrypt.verify(plain, hashed)
        if bcrypt:
            return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except Exception:
        return False
    return False


def seed_user_if_needed() -> None:
    """Seed the single client user from config (secrets). Idempotent. In-memory only."""
    import streamlit as st
    from src.config import get_config
    cfg = get_config()
    email = (cfg.get("SEED_CLIENT_EMAIL") or "").strip().lower()
    password = (cfg.get("SEED_CLIENT_PASSWORD") or "").strip()
    role = (cfg.get("SEED_CLIENT_ROLE") or "client").strip().lower()
    if not email or not password:
        return
    if email in _users:
        return
    _users[email] = {
        "email": email,
        "password_hash": _hash_password(password),
        "role": role,
    }


def login(email: str, password: str) -> bool:
    """Verify credentials and set session. Returns True on success."""
    import streamlit as st
    email = (email or "").strip().lower()
    if not email or not password:
        return False
    user = _users.get(email)
    if not user or not _verify_password(password, user.get("password_hash", "")):
        return False
    st.session_state.auth_user = user
    st.session_state.auth_role = user.get("role") or "client"
    st.session_state.auth_email = user.get("email")
    return True


def logout() -> None:
    """Clear auth from session (legacy + JWT)."""
    import streamlit as st
    for key in ("auth_user", "auth_role", "auth_email", "auth_token"):
        if key in st.session_state:
            del st.session_state[key]


def require_login() -> None:
    """Require logged-in user (auth_email or auth_token). st.stop() if not."""
    import streamlit as st
    if st.session_state.get("auth_email") or st.session_state.get("auth_token"):
        return
    st.warning("Please log in to continue.")
    st.stop()


def require_role(roles: list[str] | tuple[str]) -> None:
    """Require current user role in allowed list. Call after require_login(). st.stop() if not."""
    import streamlit as st
    role = (st.session_state.get("auth_role") or "").strip().lower()
    allowed = [r.strip().lower() for r in roles]
    if role not in allowed:
        st.error("🔒 You do not have permission to view this page.")
        st.stop()


def current_user() -> Optional[dict[str, Any]]:
    """Return current user dict (email, role) or None."""
    import streamlit as st
    if not st.session_state.get("auth_email"):
        return None
    return {
        "email": st.session_state.get("auth_email"),
        "role": (st.session_state.get("auth_role") or "client").strip().lower(),
    }
