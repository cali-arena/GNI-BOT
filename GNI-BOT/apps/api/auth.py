"""
JWT + API key authentication for control/admin endpoints.
User auth: login/register (email + bcrypt) -> JWT; get_current_user dependency.
When neither JWT_SECRET nor API_KEY is set, auth is disabled (backward compat).
Uses secrets provider (no hardcoding).
"""
import time
from typing import Any, Optional

from fastapi import Depends, HTTPException, Request, Security
from fastapi.security import APIKeyHeader, HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from apps.shared.secrets import get_secret

try:
    import jwt
except ImportError:
    jwt = None

try:
    from passlib.hash import bcrypt as passlib_bcrypt
except ImportError:
    passlib_bcrypt = None

JWT_SECRET = get_secret("JWT_SECRET")
API_KEY = get_secret("API_KEY") or get_secret("ADMIN_API_KEY")
JWT_ALGORITHM = "HS256"
JWT_EXPIRY_SECONDS = int(get_secret("JWT_EXPIRY_SECONDS", "86400"))  # 24h

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)
http_bearer = HTTPBearer(auto_error=False)


# --- Password hashing (bcrypt) ---
def hash_password(plain: str) -> str:
    if not passlib_bcrypt:
        raise ValueError("passlib[bcrypt] required for user auth")
    return passlib_bcrypt.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    if not plain or not hashed or not passlib_bcrypt:
        return False
    try:
        return passlib_bcrypt.verify(plain, hashed)
    except Exception:
        return False


def auth_required() -> bool:
    """True if any auth is configured (JWT or API key)."""
    return bool(JWT_SECRET or API_KEY)


def _verify_api_key(key: Optional[str]) -> bool:
    if not API_KEY or not key:
        return False
    return key.strip() == API_KEY


def _verify_jwt(token: str) -> bool:
    if not JWT_SECRET or not jwt:
        return False
    try:
        jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return True
    except Exception:
        return False


async def require_auth(
    request: Request,
    api_key: Optional[str] = Security(api_key_header),
    credentials: Optional[HTTPAuthorizationCredentials] = Security(http_bearer),
) -> None:
    """
    Dependency: require valid API key or JWT Bearer token for control endpoints.
    When auth is disabled (no JWT_SECRET, no API_KEY), passes without check.
    """
    if not auth_required():
        return
    if api_key and _verify_api_key(api_key):
        return
    if credentials and credentials.credentials and _verify_jwt(credentials.credentials):
        return
    raise HTTPException(status_code=401, detail="Unauthorized")


def create_token(subject: str = "api") -> str:
    """Create JWT. subject is typically user id (str). Requires JWT_SECRET and PyJWT."""
    if not JWT_SECRET or not jwt:
        raise ValueError("JWT_SECRET required and PyJWT must be installed")
    payload = {"sub": str(subject), "exp": int(time.time()) + JWT_EXPIRY_SECONDS}
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_jwt_payload(token: str) -> Optional[dict[str, Any]]:
    """Decode JWT and return payload or None if invalid/expired."""
    if not JWT_SECRET or not jwt or not token:
        return None
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except Exception:
        return None


def _get_current_user_impl(
    credentials: Optional[HTTPAuthorizationCredentials],
    session: Session,
) -> "User":
    from apps.api.db.models import User

    if not credentials or not credentials.credentials:
        raise HTTPException(status_code=401, detail="Missing Authorization header")
    payload = decode_jwt_payload(credentials.credentials)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    sub = payload.get("sub")
    if not sub:
        raise HTTPException(status_code=401, detail="Invalid token")
    try:
        user_id = int(sub)
    except (TypeError, ValueError):
        raise HTTPException(status_code=401, detail="Invalid token")
    user = session.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Security(http_bearer),
    session: Session = Depends(__import__("db", fromlist=["get_db_dependency"]).get_db_dependency),
) -> "User":
    """Dependency: require valid JWT Bearer with user sub; return User from DB."""
    return _get_current_user_impl(credentials, session)
