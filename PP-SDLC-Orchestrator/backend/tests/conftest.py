import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.base import Base
from app.models import *  # noqa: F401,F403 - populate Base.metadata


def _fresh_sqlite_engine(db_path) -> Engine:
    """A schema-migrated SQLite engine at `db_path`, via `Base.metadata.create_all`
    rather than Alembic — the migration path itself has its own dedicated
    coverage in test_migration.py, so fixtures don't need to re-run it.
    """
    engine = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    return engine


@pytest.fixture(autouse=True)
def isolate_generated_artefacts(tmp_path, monkeypatch):
    """Every test's mock-adapter output goes to a per-test temp dir instead
    of the real repo's 05_Generated_Artefacts/ — without this, running the
    suite repeatedly litters the working tree with UUID-named test output.
    """
    monkeypatch.setenv("PPSDLC_GENERATED_ARTEFACTS_DIR", str(tmp_path / "generated_artefacts"))
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def db_session(tmp_path):
    """A SQLAlchemy Session for service-layer tests that talk to models
    directly (OrchestratorService, etc.) — no HTTP layer involved.
    """
    engine = _fresh_sqlite_engine(tmp_path / "test.db")
    session = Session(bind=engine)
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


@pytest.fixture
def api_client(tmp_path, monkeypatch):
    """A TestClient for HTTP-level tests, backed by its own isolated temp
    SQLite DB.

    Each FastAPI app instance builds its own DB session factory inside
    `lifespan()` (see app/main.py) by calling `get_settings()` at startup —
    that call happens fresh every time a TestClient's `with` block is
    entered, not once at import time. So setting the env var and clearing
    the settings cache *before* entering the `with` block is sufficient to
    isolate this test's database; no module-reload trick is needed.
    """
    db_path = tmp_path / "api_test.db"
    monkeypatch.setenv("PPSDLC_DATABASE_URL", f"sqlite:///{db_path}")
    get_settings.cache_clear()
    _fresh_sqlite_engine(db_path).dispose()

    from app.main import app

    with TestClient(app) as client:
        yield client

    get_settings.cache_clear()
