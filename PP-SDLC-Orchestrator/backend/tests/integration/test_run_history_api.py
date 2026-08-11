"""Covers GET /projects/{id}/runs — the run-history/audit endpoint that
was missing since session 1 (documented repeatedly as "no list runs
endpoint yet"). This is what lets the frontend restore an in-flight
review after a page refresh instead of losing track of it, and gives a
tester full visibility into every run/decision/artefact across a
project's lifecycle, not just the most recent one.
"""


def _create_reviewer(api_client, email="history.reviewer@example.test"):
    return api_client.post("/users", json={"email": email, "role": "Reviewer"}).json()["id"]


def test_run_history_lists_every_run_across_phases(api_client):
    project = api_client.post("/projects", json={"name": "Run History Coverage"}).json()
    reviewer_id = _create_reviewer(api_client)

    analysis_run = api_client.post(
        f"/projects/{project['id']}/runs", json={"task_request": "Draft requirements"}
    ).json()
    api_client.post(
        f"/runs/{analysis_run['id']}/review",
        json={"reviewer_id": reviewer_id, "decision": "approved", "comments": []},
    )
    ux_run = api_client.post(
        f"/projects/{project['id']}/runs", json={"task_request": "Design the experience"}
    ).json()

    history = api_client.get(f"/projects/{project['id']}/runs").json()

    assert len(history) == 2
    assert history[0]["id"] == analysis_run["id"]
    assert history[0]["phase"] == "analysis"
    assert history[0]["task_request"] == "Draft requirements"
    assert history[0]["review_decision"] == "approved"
    assert history[0]["artefact_types"] == ["requirement_specification"]
    assert history[0]["state"] == "completed"

    assert history[1]["id"] == ux_run["id"]
    assert history[1]["phase"] == "ux_design"
    assert history[1]["task_request"] == "Design the experience"
    assert history[1]["review_decision"] is None  # not yet reviewed
    assert set(history[1]["artefact_types"]) == {"ux_design_specification", "ux_interactive_prototype"}
    assert history[1]["state"] == "waiting_for_human_review"


def test_run_history_reflects_rework_as_a_second_run_in_same_phase(api_client):
    project = api_client.post("/projects", json={"name": "Rework Coverage"}).json()
    reviewer_id = _create_reviewer(api_client, email="rework.reviewer@example.test")

    first_run = api_client.post(
        f"/projects/{project['id']}/runs", json={"task_request": "Draft requirements"}
    ).json()
    api_client.post(
        f"/runs/{first_run['id']}/review",
        json={"reviewer_id": reviewer_id, "decision": "rework_required", "comments": ["Needs more detail"]},
    )
    second_run = api_client.post(
        f"/projects/{project['id']}/runs", json={"task_request": "Draft requirements, take two"}
    ).json()

    history = api_client.get(f"/projects/{project['id']}/runs").json()

    assert len(history) == 2
    assert history[0]["run_number"] == 1
    assert history[0]["review_decision"] == "rework_required"
    assert history[1]["run_number"] == 2
    assert history[1]["phase"] == "analysis"  # rework keeps the same phase


def test_run_history_for_unknown_project_returns_404(api_client):
    resp = api_client.get("/projects/does-not-exist/runs")
    assert resp.status_code == 404


def test_run_history_for_project_with_no_runs_is_empty(api_client):
    project = api_client.post("/projects", json={"name": "No Runs Yet"}).json()

    history = api_client.get(f"/projects/{project['id']}/runs").json()

    assert history == []


def test_run_history_task_request_survives_a_failed_run(api_client, monkeypatch):
    """task_request must be readable even for a run that never reached
    completion — it's read from the run_started audit event, logged before
    the adapter is even invoked, not from anything the adapter produces.
    """
    from app.adapters.model_providers import factory as model_provider_factory
    from app.adapters.model_providers.base import ModelProviderError

    class _AlwaysFailsProvider:
        def complete(self, *, system, user):
            raise ModelProviderError("simulated network failure")

    monkeypatch.setattr(model_provider_factory, "get_model_provider", lambda: _AlwaysFailsProvider())

    project = api_client.post("/projects", json={"name": "Failed Run Task Visibility"}).json()
    resp = api_client.post(
        f"/projects/{project['id']}/runs", json={"task_request": "This run is doomed to fail"}
    )
    assert resp.status_code == 409  # OrchestrationError wraps the adapter failure

    history = api_client.get(f"/projects/{project['id']}/runs").json()
    assert len(history) == 1
    assert history[0]["state"] == "failed"
    assert history[0]["task_request"] == "This run is doomed to fail"
