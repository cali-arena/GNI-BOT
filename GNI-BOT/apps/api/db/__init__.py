"""
DB engine, session, and models. Re-exports from session.py and models for compatibility.
"""
from .models import Base  # noqa: F401 — keep so metadata is populated for create_all / Alembic
from .models import (
    DeadLetterQueue,
    Draft,
    EventsLog,
    Item,
    Publication,
    RawItem,
    Settings,
    Source,
    User,
    WhatsAppSession,
)
from .session import (
    SessionLocal,
    check_db,
    engine,
    get_db,
    get_db_dependency,
    get_engine,
    init_db,
)

__all__ = [
    "Base",
    "DeadLetterQueue",
    "Draft",
    "EventsLog",
    "Item",
    "Publication",
    "RawItem",
    "Settings",
    "Source",
    "User",
    "WhatsAppSession",
    "SessionLocal",
    "check_db",
    "engine",
    "get_db",
    "get_db_dependency",
    "get_engine",
    "init_db",
]
