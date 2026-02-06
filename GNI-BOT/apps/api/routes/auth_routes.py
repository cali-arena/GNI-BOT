"""
Auth routes: login/register (email+password -> JWT), token exchange (API key -> JWT).
"""
from fastapi import APIRouter, Depends, HTTPException, Security
from sqlalchemy.orm import Session

from auth import (
    API_KEY,
    api_key_header,
    auth_required,
    create_token,
    get_current_user,
    hash_password,
    verify_password,
)
from apps.api.db import get_db_dependency
from apps.api.db.models import User
from schemas import LoginIn, RegisterIn, TokenOut

router = APIRouter(prefix="/auth", tags=["auth"])


def _user_by_email(session: Session, email: str) -> User | None:
    return session.query(User).filter(User.email == (email or "").strip().lower()).first()


@router.post("/login", response_model=TokenOut)
def login(body: LoginIn, session: Session = Depends(get_db_dependency)):
    """
    Login with email/password. Returns JWT as access_token (Bearer).
    Requires JWT_SECRET and passlib[bcrypt].
    """
    if not auth_required():
        raise HTTPException(status_code=503, detail="Auth not configured (JWT_SECRET required)")
    email = (body.email or "").strip().lower()
    if not email or not body.password:
        raise HTTPException(status_code=400, detail="email and password required")
    user = _user_by_email(session, email)
    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    token = create_token(subject=str(user.id))
    return TokenOut(access_token=token)


@router.post("/register", response_model=TokenOut)
def register(body: RegisterIn, session: Session = Depends(get_db_dependency)):
    """
    Register a new user (email + password). Returns JWT. Duplicate email returns 400.
    """
    if not auth_required():
        raise HTTPException(status_code=503, detail="Auth not configured (JWT_SECRET required)")
    email = (body.email or "").strip().lower()
    if not email or not body.password:
        raise HTTPException(status_code=400, detail="email and password required")
    if _user_by_email(session, email):
        raise HTTPException(status_code=400, detail="Email already registered")
    user = User(email=email, password_hash=hash_password(body.password))
    session.add(user)
    session.commit()
    session.refresh(user)
    token = create_token(subject=str(user.id))
    return TokenOut(access_token=token)


@router.get("/me")
def me(user: User = Depends(get_current_user)):
    """Return current user (requires JWT Bearer)."""
    return {"id": user.id, "email": user.email}


@router.post("/token")
def get_token(api_key: str = Security(api_key_header)):
    """
    Exchange API key for JWT. Requires X-API-Key header.
    Returns JWT for use as Bearer token. Requires JWT_SECRET and API_KEY to be set.
    """
    if not auth_required():
        return {"token": None, "message": "Auth not configured"}
    if not api_key or api_key.strip() != API_KEY:
        raise HTTPException(status_code=401, detail="Unauthorized")
    try:
        token = create_token()
        return {"token": token, "expires_in": 86400}
    except ValueError as e:
        raise HTTPException(status_code=500, detail=str(e))
