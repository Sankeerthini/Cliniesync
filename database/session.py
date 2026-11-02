"""Engine / session helpers shared by ETL and backend."""
from __future__ import annotations

from contextlib import contextmanager
from functools import lru_cache
from typing import Iterator

from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from common.settings import get_settings
from database.models import Base
from database.views import ANALYTICS_VIEWS


@lru_cache
def get_engine() -> Engine:
    url = get_settings().database_url
    kwargs = {"future": True}
    if url.startswith("sqlite"):
        kwargs["connect_args"] = {"check_same_thread": False}
    engine = create_engine(url, **kwargs)
    if url.startswith("sqlite"):

        @event.listens_for(engine, "connect")
        def _sqlite_pragmas(dbapi_conn, _):  # pragma: no cover - trivial
            cur = dbapi_conn.cursor()
            cur.execute("PRAGMA journal_mode=WAL")
            cur.execute("PRAGMA foreign_keys=ON")
            cur.close()

    return engine


@lru_cache
def _session_factory() -> sessionmaker:
    return sessionmaker(bind=get_engine(), expire_on_commit=False, future=True)


@contextmanager
def session_scope() -> Iterator[Session]:
    session = _session_factory()()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_session() -> Iterator[Session]:
    """FastAPI dependency. Use with Depends(get_session, scope="function") so the commit happens
    BEFORE the response is sent (the UI re-fetches immediately after writes)."""
    with session_scope() as s:
        yield s


def init_db(drop: bool = False) -> None:
    engine = get_engine()
    with engine.begin() as conn:
        for name in ANALYTICS_VIEWS:
            conn.execute(text(f"DROP VIEW IF EXISTS {name}"))
    if drop:
        Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    create_views()


def create_views() -> None:
    with get_engine().begin() as conn:
        for name, sql in ANALYTICS_VIEWS.items():
            conn.execute(text(f"DROP VIEW IF EXISTS {name}"))
            conn.execute(text(f"CREATE VIEW {name} AS {sql}"))


@lru_cache
def _read_only_engine() -> Engine:
    """Separate engine WITHOUT pooling, so a read-only connection can never be reused for writes."""
    from sqlalchemy.pool import NullPool

    url = get_settings().database_url
    sqlite = url.startswith("sqlite")
    engine = create_engine(url, poolclass=NullPool,
                           connect_args={"check_same_thread": False} if sqlite else {})

    @event.listens_for(engine, "connect")
    def _ro(dbapi_conn, _):  # pragma: no cover - trivial
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA query_only = ON" if sqlite else "SET SESSION CHARACTERISTICS AS TRANSACTION READ ONLY")
        cur.close()

    return engine


def read_only_connection():
    """A connection that refuses writes - used for LLM-generated SQL."""
    return _read_only_engine().connect()
