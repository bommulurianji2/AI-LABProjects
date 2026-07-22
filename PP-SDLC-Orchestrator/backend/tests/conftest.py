import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.base import Base
from app.models import *  # noqa: F401,F403 - populate Base.metadata


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
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    session = Session(bind=engine)
    try:
        yield session
    finally:
        session.close()
        engine.dispose()
