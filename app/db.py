from __future__ import annotations

from functools import lru_cache
from typing import Iterator

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from .config import engine_options, get_settings


@lru_cache(maxsize=1)
def get_engine() -> Engine:
    url = get_settings().database_url
    engine = create_engine(url, **engine_options(url))
    if url.startswith("sqlite"):
        # SQLite (tests, quick local runs) only enforces ON DELETE CASCADE when asked to.
        @event.listens_for(engine, "connect")
        def _fk_on(dbapi_conn, _record):
            dbapi_conn.execute("PRAGMA foreign_keys=ON")
    return engine


@lru_cache(maxsize=1)
def _sessionmaker() -> sessionmaker:
    return sessionmaker(bind=get_engine(), expire_on_commit=False)


def get_db() -> Iterator[Session]:
    db = _sessionmaker()()
    try:
        yield db
    finally:
        db.close()


def new_session() -> Session:
    return _sessionmaker()()
