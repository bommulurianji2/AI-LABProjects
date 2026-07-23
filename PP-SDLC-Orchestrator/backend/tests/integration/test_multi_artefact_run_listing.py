"""Regression coverage for a real bug found via manual UI testing: a run
that produces more than one artefact (the UX Design Agent's spec +
prototype) must have every one of them visible and individually
identifiable through the API — not just the most recent one.
"""

from app.models.artefact import ArtefactVersion
from app.models.user import User
from tests.helpers import make_orchestrator, run_phase_to_approval


def test_multi_artefact_run_lists_every_artefact_with_its_type(db_session):
    orchestrator = make_orchestrator(db_session)
    reviewer = User(email="ux.reviewer@example.test", role="Reviewer")
    db_session.add(reviewer)
    db_session.commit()

    project = orchestrator.create_project("Employee Onboarding")
    run_phase_to_approval(orchestrator, project, reviewer_id=reviewer.id, task_request="Draft requirements")

    ux_run = orchestrator.start_run(project, task_request="Design the onboarding experience")

    versions = db_session.query(ArtefactVersion).filter_by(run_id=ux_run.id).all()
    assert len(versions) == 2
    assert {v.artefact_type for v in versions} == {"ux_design_specification", "ux_interactive_prototype"}


def test_artefact_versions_endpoint_exposes_artefact_type_per_version(api_client):
    project = api_client.post("/projects", json={"name": "Onboarding"}).json()

    analysis_run = api_client.post(
        f"/projects/{project['id']}/runs", json={"task_request": "Draft requirements"}
    ).json()
    api_client.post(
        f"/runs/{analysis_run['id']}/review",
        json={"reviewer_id": "ux.reviewer@example.test", "decision": "approved", "comments": []},
    )

    ux_run = api_client.post(
        f"/projects/{project['id']}/runs", json={"task_request": "Design the onboarding experience"}
    ).json()

    versions = api_client.get(f"/runs/{ux_run['id']}/artefact-versions").json()
    assert len(versions) == 2
    assert {v["artefact_type"] for v in versions} == {"ux_design_specification", "ux_interactive_prototype"}
    assert all(v["version_label"] == "v0.1" for v in versions)
