"""HTTP-level end-to-end test: create project -> start run -> fetch artefact
version -> submit review -> assert phase unlock. Each app instance builds
its own session factory at lifespan startup (see app/main.py), so pointing
PPSDLC_DATABASE_URL at a temp file before constructing the TestClient is
enough to fully isolate this test's database.
"""

from fastapi.testclient import TestClient

from app.config import get_settings
from app.db.base import Base
from app.models import *  # noqa: F401,F403 - populate Base.metadata


def _fresh_app(tmp_path, monkeypatch):
    db_path = tmp_path / "api_test.db"
    monkeypatch.setenv("PPSDLC_DATABASE_URL", f"sqlite:///{db_path}")
    get_settings.cache_clear()

    # Import (or re-import) after the env var is set so any module-level
    # settings reads inside app.main pick up the temp DB.
    import importlib

    import app.main as app_main

    importlib.reload(app_main)
    return app_main.app


def _create_schema(database_url: str) -> None:
    from sqlalchemy import create_engine

    engine = create_engine(database_url)
    Base.metadata.create_all(engine)
    engine.dispose()


def test_full_orchestrated_loop_over_http(tmp_path, monkeypatch):
    app = _fresh_app(tmp_path, monkeypatch)
    _create_schema(get_settings().database_url)

    with TestClient(app) as client:
        agents = client.get("/agents").json()
        assert any(a["id"] == "analysis" for a in agents)

        create_resp = client.post("/projects", json={"name": "Employee Leave Request"})
        assert create_resp.status_code == 201
        project = create_resp.json()
        assert project["current_phase"] == "analysis"
        assert project["phase_status"] == "pending"

        run_resp = client.post(
            f"/projects/{project['id']}/runs", json={"task_request": "Build an employee leave request workflow"}
        )
        assert run_resp.status_code == 201
        run = run_resp.json()
        assert run["state"] == "waiting_for_human_review"

        version_resp = client.get(f"/runs/{run['id']}/artefact-version")
        assert version_resp.status_code == 200
        version = version_resp.json()
        assert version["version_label"] == "v0.1"
        assert version["status"] == "draft"

        # simulate a reviewer user existing (session-1 has no auth yet - pass a raw id)
        review_resp = client.post(
            f"/runs/{run['id']}/review",
            json={"reviewer_id": "test-reviewer", "decision": "approved", "comments": ["Looks good"]},
        )
        assert review_resp.status_code == 200
        updated_project = review_resp.json()
        assert updated_project["current_phase"] == "ux_design"
        assert updated_project["phase_status"] == "pending"

        run_status = client.get(f"/runs/{run['id']}").json()
        assert run_status["state"] == "completed"
