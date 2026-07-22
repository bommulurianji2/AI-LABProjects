import sqlite3
from pathlib import Path

from alembic import command
from alembic.config import Config

from app.models import __all__ as model_names

BACKEND_DIR = Path(__file__).resolve().parent.parent.parent

EXPECTED_TABLES = {
    "users",
    "projects",
    "agent_defs",
    "agent_runs",
    "run_events",
    "artefacts",
    "artefact_versions",
    "reviews",
    "review_comments",
}


def test_initial_migration_applies_cleanly_to_fresh_sqlite(tmp_path):
    db_path = tmp_path / "fresh.db"
    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    cfg.set_main_option("sqlalchemy.url", f"sqlite:///{db_path}")

    command.upgrade(cfg, "head")

    conn = sqlite3.connect(db_path)
    tables = {r[0] for r in conn.execute("select name from sqlite_master where type='table'")}
    conn.close()

    assert EXPECTED_TABLES <= tables


def test_all_nine_session1_models_are_registered():
    assert set(model_names) == {
        "AgentDef",
        "AgentRun",
        "RunEvent",
        "Artefact",
        "ArtefactVersion",
        "Project",
        "Review",
        "ReviewComment",
        "User",
    }
