"""Extends the chain to a seventh real agent: ... -> Build -> Validation/QA.
Confirms the Validation Report is generated and approval unlocks test.
"""

from docx import Document

from app.domain.enums import ArtefactVersionStatus, PhaseStatus
from app.models.artefact import ArtefactVersion
from app.models.user import User
from tests.helpers import make_orchestrator, run_phase_to_approval


def test_chain_through_validation_qa_unlocks_test(db_session):
    orchestrator = make_orchestrator(db_session)
    reviewer = User(email="qa.reviewer@example.test", role="Reviewer")
    db_session.add(reviewer)
    db_session.commit()

    project = orchestrator.create_project("Contract and Approval Management")

    run_phase_to_approval(orchestrator, project, reviewer_id=reviewer.id, task_request="Draft requirements")
    run_phase_to_approval(orchestrator, project, reviewer_id=reviewer.id, task_request="Design the experience")
    run_phase_to_approval(
        orchestrator, project, reviewer_id=reviewer.id, task_request="Design the technical architecture"
    )
    run_phase_to_approval(orchestrator, project, reviewer_id=reviewer.id, task_request="Design the data model")
    run_phase_to_approval(
        orchestrator, project, reviewer_id=reviewer.id, task_request="Define governance and security controls"
    )
    run_phase_to_approval(orchestrator, project, reviewer_id=reviewer.id, task_request="Build the solution")
    assert project.current_phase == "validation_qa"

    qa_run = run_phase_to_approval(
        orchestrator, project, reviewer_id=reviewer.id, task_request="Independently validate the build"
    )
    assert project.current_phase == "test"
    assert project.phase_status == PhaseStatus.PENDING.value

    versions = db_session.query(ArtefactVersion).filter_by(run_id=qa_run.id).all()
    assert len(versions) == 1
    version = versions[0]
    db_session.refresh(version)
    assert version.version_label == "v1.0"
    assert version.status == ArtefactVersionStatus.BASELINE.value

    doc = Document(version.file_path)
    full_text = "\n".join(p.text for p in doc.paragraphs)
    assert "Pass with findings" in full_text
