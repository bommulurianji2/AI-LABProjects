"""Proves the chain now spans two real agents: Analysis -> UX Design.
Analysis approval unlocks ux_design; running and approving the UX Design
agent (which produces TWO artefacts per run) must promote both to baseline
and unlock technical_design.
"""

from docx import Document

from app.agents_registry.registry import AgentRegistry
from app.domain.enums import ArtefactVersionStatus, PhaseStatus, ReviewDecision
from app.models.artefact import ArtefactVersion
from app.models.user import User
from app.orchestrator.service import OrchestratorService, sync_agent_defs


def _make_orchestrator(session):
    registry = AgentRegistry()
    registry.load()
    assert registry.failures == [], f"registry failures: {registry.failures}"
    sync_agent_defs(session, registry.list_agents())
    return OrchestratorService(session, registry)


def test_analysis_then_ux_design_chain_promotes_both_artefacts(db_session):
    orchestrator = _make_orchestrator(db_session)
    reviewer = User(email="ux.reviewer@example.test", role="Reviewer")
    db_session.add(reviewer)
    db_session.commit()

    project = orchestrator.create_project("Employee Onboarding")

    analysis_run = orchestrator.start_run(project, task_request="Draft onboarding requirements")
    orchestrator.submit_review(analysis_run, reviewer_id=reviewer.id, decision=ReviewDecision.APPROVED)
    assert project.current_phase == "ux_design"
    assert project.phase_status == PhaseStatus.PENDING.value

    ux_run = orchestrator.start_run(project, task_request="Design the onboarding experience")
    assert ux_run.agent_id == "ux_design"
    assert project.phase_status == PhaseStatus.AWAITING_REVIEW.value

    versions = db_session.query(ArtefactVersion).filter_by(run_id=ux_run.id).all()
    assert len(versions) == 2
    assert any(v.file_path.endswith(".docx") for v in versions)
    assert any(v.file_path.endswith(".html") for v in versions)
    for v in versions:
        assert v.version_label == "v0.1"
        assert v.status == ArtefactVersionStatus.DRAFT.value

    spec_version = next(v for v in versions if v.file_path.endswith(".docx"))
    doc = Document(spec_version.file_path)
    full_text = "\n".join(p.text for p in doc.paragraphs)
    assert "SCR-001" in full_text
    assert "Employee Onboarding" in full_text

    prototype_version = next(v for v in versions if v.file_path.endswith(".html"))
    html_text = open(prototype_version.file_path, encoding="utf-8").read()
    assert "Employee Onboarding" in html_text
    assert "SCR-001" in html_text

    final_project = orchestrator.submit_review(ux_run, reviewer_id=reviewer.id, decision=ReviewDecision.APPROVED)
    assert final_project.current_phase == "technical_design"
    assert final_project.phase_status == PhaseStatus.PENDING.value

    for v in versions:
        db_session.refresh(v)
        assert v.version_label == "v1.0"
        assert v.status == ArtefactVersionStatus.BASELINE.value


def test_ux_prototype_escapes_malicious_project_name(db_session, tmp_path):
    """A project name containing an HTML/script payload must not be
    reflected unescaped into the generated interactive prototype."""
    orchestrator = _make_orchestrator(db_session)
    reviewer = User(email="ux.reviewer@example.test", role="Reviewer")
    db_session.add(reviewer)
    db_session.commit()

    malicious_name = '<script>alert(1)</script>"><img src=x onerror=alert(2)>'
    project = orchestrator.create_project(malicious_name)

    analysis_run = orchestrator.start_run(project, task_request="Draft requirements")
    orchestrator.submit_review(analysis_run, reviewer_id=reviewer.id, decision=ReviewDecision.APPROVED)

    ux_run = orchestrator.start_run(project, task_request="Design the experience")
    versions = db_session.query(ArtefactVersion).filter_by(run_id=ux_run.id).all()
    prototype_version = next(v for v in versions if v.file_path.endswith(".html"))
    html_text = open(prototype_version.file_path, encoding="utf-8").read()

    # The payload must not survive as live markup — no raw "<script>" or "<img"
    # tag structure. It's fine for the inert text of the payload to appear
    # escaped (as &lt;...&gt;) since it can no longer execute.
    assert "<script>" not in html_text
    assert "<img" not in html_text
    assert "&lt;script&gt;" in html_text
    assert "&lt;img" in html_text
