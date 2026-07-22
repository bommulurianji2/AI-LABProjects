from collections.abc import Iterator

from fastapi import Request
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker


def build_session_factory(database_url: str) -> sessionmaker:
    # check_same_thread=False is required for SQLite when the same connection pool
    # is shared across FastAPI's threadpool-executed request handlers; it has no
    # effect on Postgres/Azure SQL, so this stays portable.
    connect_args = {"check_same_thread": False} if database_url.startswith("sqlite") else {}
    engine = create_engine(database_url, connect_args=connect_args)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False)


def get_session(request: Request) -> Iterator[Session]:
    """FastAPI dependency — reads the per-app session factory built at
    startup (see `main.py` lifespan), so each app instance (including test
    instances pointed at a temp DB) is fully self-contained.
    """
    session = request.app.state.session_factory()
    try:
        yield session
    finally:
        session.close()
