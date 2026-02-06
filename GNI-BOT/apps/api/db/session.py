"""
DB engine and session. Connection pooling with defensive handling.
Session logic lives here; db/__init__.py re-exports for compatibility.
Uses secrets provider for DATABASE_URL (no hardcoding).
"""
import logging
from contextlib import contextmanager
from typing import Generator

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session, sessionmaker

from apps.shared.config import DATABASE_URL_DEFAULT
from apps.shared.secrets import get_secret

logger = logging.getLogger(__name__)

# Pool config: env overrides with safe defaults
POOL_SIZE = int(get_secret("DB_POOL_SIZE", "5"))
MAX_OVERFLOW = int(get_secret("DB_MAX_OVERFLOW", "10"))
POOL_RECYCLE = int(get_secret("DB_POOL_RECYCLE", "1800"))  # 30 min
POOL_TIMEOUT = int(get_secret("DB_POOL_TIMEOUT", "30"))


def get_engine() -> Engine:
    url = get_secret("DATABASE_URL", DATABASE_URL_DEFAULT)
    engine = create_engine(
        url,
        pool_size=POOL_SIZE,
        max_overflow=MAX_OVERFLOW,
        pool_pre_ping=True,
        pool_recycle=POOL_RECYCLE,
        pool_timeout=POOL_TIMEOUT,
    )
    return engine


engine = get_engine()
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
    expire_on_commit=False,
)


def init_db() -> None:
    """Run Alembic migrations (alembic upgrade head). Idempotent."""
    import subprocess
    import sys
    from pathlib import Path

    _here = Path(__file__).resolve().parent  # db/
    # In API Docker container: WORKDIR /app, so /app/alembic.ini and /app/alembic/ exist.
    if Path("/app/alembic.ini").exists():
        repo_root = Path("/app")
    else:
        # Local or worker: find repo root by walking up from db/
        for candidate in (_here.parent.parent.parent.parent, _here.parent.parent.parent, _here.parent.parent):
            if (candidate / "alembic.ini").exists():
                repo_root = candidate
                break
        else:
            repo_root = _here.parent.parent
    repo_root = repo_root.resolve()
    if not (repo_root / "alembic.ini").exists():
        raise RuntimeError(f"alembic.ini not found in {repo_root}; expected at repo root (e.g. /app in Docker)")
    alembic_cmd = [sys.executable, "-m", "alembic", "upgrade", "head"]
    result = subprocess.run(alembic_cmd, cwd=str(repo_root), capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"alembic upgrade head failed: {result.stderr or result.stdout}")


def _safe_close_session(session: Session | None) -> None:
    """Defensive close: always releases connection; logs on error."""
    if session is None:
        return
    try:
        session.close()
    except DBAPIError as e:
        logger.warning("Session close after DB error: %s", e)
    except Exception as e:
        logger.warning("Session close error: %s", e)


def check_db() -> bool:
    """Return True if DB is reachable. Uses pool; recycles stale connections via pool_pre_ping."""
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except DBAPIError as e:
        logger.debug("DB unreachable: %s", e)
        return False
    except Exception:
        return False


@contextmanager
def get_db() -> Generator[Session, None, None]:
    """Context manager: yields session, commits on success, rollback on error, always closes."""
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        _safe_close_session(session)


def get_db_dependency() -> Generator[Session, None, None]:
    """FastAPI dependency: yields session; caller commits. Always closes on exit."""
    session = SessionLocal()
    try:
        yield session
    finally:
        _safe_close_session(session)
