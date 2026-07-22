from docx import Document

from app.agents_registry.registry import AgentRegistry
from app.domain.enums import ArtefactVersionStatus, PhaseStatus, ReviewDecision, RunState
from app.models.artefact import ArtefactVersion
from app.models.review import Review, ReviewComment
from app.models.user import User
from app.orchestrator.service import OrchestratorService, sync_agent_defs


def _make_orchestrator(session):
    registry = AgentRegistry()
    registry.load()  # real 03_Agent_Skills dir - must find the analysis agent
    assert registry.get_agent("analysis") is not None, f"registry failures: {registry.failures}"
    sync_agent_defs(session, registry.list_agents())
    return OrchestratorService(session, registry)


def _latest_version_for_run(session, run):
    return session.query(ArtefactVersion).filter_by(run_id=run.id).one()


def test_full_orchestrated_loop_create_run_review_approve(db_session):
    orchestrator = _make_orchestrator(db_session)
    reviewer = User(email="qa.reviewer@example.test", role="Reviewer")
    db_session.add(reviewer)
    db_session.commit()

    project = orchestrator.create_project("Employee Leave Request")
    assert project.current_phase == "analysis"
    assert project.phase_status == PhaseStatus.PENDING.value

    run = orchestrator.start_run(project, task_request="Build an employee leave request workflow")
    assert run.state == RunState.WAITING_FOR_HUMAN_REVIEW.value
    assert run.run_number == 1
    assert project.phase_status == PhaseStatus.AWAITING_REVIEW.value

    version = _latest_version_for_run(db_session, run)
    assert version.version_label == "v0.1"
    assert version.status == ArtefactVersionStatus.DRAFT.value

    doc = Document(version.file_path)
    full_text = "\n".join(p.text for p in doc.paragraphs)
    assert "REQ-001" in full_text
    assert "Employee Leave Request" in full_text

    updated_project = orchestrator.submit_review(
        run, reviewer_id=reviewer.id, decision=ReviewDecision.APPROVED, comments=["Looks good"]
    )

    assert run.state == RunState.COMPLETED.value
    assert updated_project.current_phase == "ux_design"
    assert updated_project.phase_status == PhaseStatus.PENDING.value

    db_session.refresh(version)
    assert version.version_label == "v1.0"
    assert version.status == ArtefactVersionStatus.BASELINE.value

    review = db_session.query(Review).filter_by(artefact_version_id=version.id).one()
    assert review.decision == ReviewDecision.APPROVED.value
    comment = db_session.query(ReviewComment).filter_by(review_id=review.id).one()
    assert comment.body == "Looks good"


def test_rework_required_keeps_phase_and_allows_rerun(db_session):
    orchestrator = _make_orchestrator(db_session)
    reviewer = User(email="qa.reviewer@example.test", role="Reviewer")
    db_session.add(reviewer)
    db_session.commit()

    project = orchestrator.create_project("Onboarding")
    run1 = orchestrator.start_run(project, task_request="Draft onboarding requirements")

    project_after_rework = orchestrator.submit_review(
        run1, reviewer_id=reviewer.id, decision=ReviewDecision.REWORK_REQUIRED
    )
    assert run1.state == RunState.REWORK_REQUIRED.value
    assert project_after_rework.current_phase == "analysis"
    assert project_after_rework.phase_status == PhaseStatus.REWORK.value

    run2 = orchestrator.start_run(project, task_request="Revise onboarding requirements")
    assert run2.run_number == 2

    version2 = _latest_version_for_run(db_session, run2)
    assert version2.version_label == "v0.2"

    final_project = orchestrator.submit_review(run2, reviewer_id=reviewer.id, decision=ReviewDecision.APPROVED)
    assert final_project.current_phase == "ux_design"


def test_cannot_start_run_while_awaiting_review(db_session):
    import pytest

    from app.orchestrator.service import OrchestrationError

    orchestrator = _make_orchestrator(db_session)
    project = orchestrator.create_project("Contract Review")
    orchestrator.start_run(project, task_request="Draft requirements")

    with pytest.raises(OrchestrationError):
        orchestrator.start_run(project, task_request="Second attempt while awaiting review")
