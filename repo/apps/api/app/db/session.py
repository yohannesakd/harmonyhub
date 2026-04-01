from __future__ import annotations

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from app.core.config import get_settings

_engine: Engine | None = None


def _is_sqlite(url: str) -> bool:
    return url.startswith("sqlite")


def get_engine() -> Engine:
    global _engine
    if _engine is None:
        settings = get_settings()
        connect_args = {"check_same_thread": False} if _is_sqlite(settings.database_url) else {}
        _engine = create_engine(settings.database_url, pool_pre_ping=True, connect_args=connect_args)
    return _engine


def reset_engine_for_tests() -> None:
    global _engine
    if _engine is not None:
        _engine.dispose()
    _engine = None


def get_db_session() -> Generator[Session, None, None]:
    session = Session(get_engine())
    try:
        yield session
    finally:
        session.close()
