"""Proves the upstream-context plumbing actually works: once Analysis is
approved, starting the next run must receive the real extracted text of
the approved Requirement Specification — not an empty dict, and not just
the original task request repeated.
"""

from app.models.user import User
from tests.helpers import make_orchestrator, run_phase_to_approval


def _capture_requests(monkeypatch, orchestrator, agent_id: str) -> list:
    captured = []
    entry = orchestrator.registry.get_agent(agent_id)
    real_adapter_class = entry.adapter_class

    class CapturingAdapter(real_adapter_class):
        def execute(self, request):
            captured.append(request)
            return super().execute(request)

    monkeypatch.setattr(entry, "adapter_class", CapturingAdapter)
    return captured


def test_ux_design_run_receives_analysis_upstream_text(db_session, monkeypatch):
    orchestrator = make_orchestrator(db_session)
    reviewer = User(email="ux.reviewer@example.test", role="Reviewer")
    db_session.add(reviewer)
    db_session.commit()

    project = orchestrator.create_project("Employee Onboarding")
    run_phase_to_approval(
        orchestrator, project, reviewer_id=reviewer.id, task_request="Draft onboarding requirements"
    )
    assert project.current_phase == "ux_design"

    captured = _capture_requests(monkeypatch, orchestrator, "ux_design")
    orchestrator.start_run(project, task_request="Design the onboarding experience")

    assert len(captured) == 1
    upstream = captured[0].upstream_artefacts_text
    assert "requirement_specification" in upstream
    assert "REQ-001" in upstream["requirement_specification"]
    assert "Employee Onboarding" in upstream["requirement_specification"]


def test_first_phase_run_has_no_upstream_text(db_session, monkeypatch):
    orchestrator = make_orchestrator(db_session)
    project = orchestrator.create_project("Fresh Project")

    captured = _capture_requests(monkeypatch, orchestrator, "analysis")
    orchestrator.start_run(project, task_request="Draft requirements")

    assert len(captured) == 1
    assert captured[0].upstream_artefacts_text == {}
