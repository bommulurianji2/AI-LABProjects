"""Covers the /users endpoints and the reviewer-existence guardrail they
exist to support: submit_review must reject a reviewer_id that doesn't
correspond to a real User row (see OrchestratorService.submit_review),
closing a real gap found via manual browser testing where any string
typed into the reviewer field was silently accepted.
"""

import pytest

from app.domain.enums import ReviewDecision
from app.models.user import User
from app.orchestrator.service import OrchestrationError
from tests.helpers import make_orchestrator


def test_create_user_returns_201_and_persists(api_client):
    resp = api_client.post("/users", json={"email": "new.reviewer@example.test", "role": "Reviewer"})

    assert resp.status_code == 201
    body = resp.json()
    assert body["email"] == "new.reviewer@example.test"
    assert body["role"] == "Reviewer"
    assert body["id"]

    listed = api_client.get("/users").json()
    assert any(u["id"] == body["id"] for u in listed)


def test_create_user_defaults_role_to_reviewer(api_client):
    resp = api_client.post("/users", json={"email": "default.role@example.test"})

    assert resp.status_code == 201
    assert resp.json()["role"] == "Reviewer"


def test_create_user_is_idempotent_by_email(api_client):
    first = api_client.post("/users", json={"email": "same.person@example.test", "role": "Reviewer"})
    assert first.status_code == 201

    second = api_client.post("/users", json={"email": "same.person@example.test", "role": "Contributor"})
    assert second.status_code == 200
    assert second.json()["id"] == first.json()["id"]
    assert second.json()["role"] == "Reviewer"  # unchanged — get-or-create, not upsert

    listed = api_client.get("/users").json()
    assert len([u for u in listed if u["email"] == "same.person@example.test"]) == 1


def test_list_users_orders_by_created_at(api_client):
    api_client.post("/users", json={"email": "first@example.test"})
    api_client.post("/users", json={"email": "second@example.test"})

    listed = api_client.get("/users").json()
    emails = [u["email"] for u in listed]
    assert emails.index("first@example.test") < emails.index("second@example.test")


def test_submit_review_with_unknown_reviewer_id_is_rejected(api_client):
    project = api_client.post("/projects", json={"name": "Reviewer Guardrail"}).json()
    run = api_client.post(
        f"/projects/{project['id']}/runs", json={"task_request": "Draft requirements"}
    ).json()

    resp = api_client.post(
        f"/runs/{run['id']}/review",
        json={"reviewer_id": "not-a-real-user-id", "decision": "approved", "comments": []},
    )

    assert resp.status_code == 409
    assert "does not exist" in resp.json()["detail"]

    # The run must be unaffected by the rejected review — still waiting.
    run_status = api_client.get(f"/runs/{run['id']}").json()
    assert run_status["state"] == "waiting_for_human_review"


def test_submit_review_with_real_reviewer_id_succeeds(api_client):
    project = api_client.post("/projects", json={"name": "Reviewer Guardrail Happy Path"}).json()
    run = api_client.post(
        f"/projects/{project['id']}/runs", json={"task_request": "Draft requirements"}
    ).json()
    reviewer_id = api_client.post("/users", json={"email": "real.reviewer@example.test"}).json()["id"]

    resp = api_client.post(
        f"/runs/{run['id']}/review",
        json={"reviewer_id": reviewer_id, "decision": "approved", "comments": []},
    )

    assert resp.status_code == 200
    assert resp.json()["current_phase"] == "ux_design"


def test_orchestrator_submit_review_raises_for_unknown_reviewer(db_session):
    orchestrator = make_orchestrator(db_session)
    project = orchestrator.create_project("Direct Service Guardrail")
    run = orchestrator.start_run(project, task_request="Draft requirements")

    with pytest.raises(OrchestrationError, match="does not exist"):
        orchestrator.submit_review(run, reviewer_id="ghost-id", decision=ReviewDecision.APPROVED)


def test_orchestrator_submit_review_succeeds_for_real_reviewer(db_session):
    orchestrator = make_orchestrator(db_session)
    reviewer = User(email="direct.service@example.test", role="Reviewer")
    db_session.add(reviewer)
    db_session.commit()

    project = orchestrator.create_project("Direct Service Happy Path")
    run = orchestrator.start_run(project, task_request="Draft requirements")

    updated_project = orchestrator.submit_review(run, reviewer_id=reviewer.id, decision=ReviewDecision.APPROVED)

    assert updated_project.current_phase == "ux_design"
