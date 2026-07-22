"""Extends the chain to a fourth real agent: ... -> Technical Design ->
Data & Integration. Confirms the Data Design Document is generated with
correct seeded DATA-00N entities and approval unlocks governance_security.
"""

from docx import Document

from app.domain.enums import ArtefactVersionStatus, PhaseStatus
from app.models.artefact import ArtefactVersion
from app.models.user import User
from tests.helpers import make_orchestrator, run_phase_to_approval


def test_chain_through_data_integration_unlocks_governance_security(db_session):
    orchestrator = make_orchestrator(db_session)
    reviewer = User(email="data.architect@example.test", role="Reviewer")
    db_session.add(reviewer)
    db_session.commit()

    project = orchestrator.create_project("Contract and Approval Management")

    run_phase_to_approval(orchestrator, project, reviewer_id=reviewer.id, task_request="Draft requirements")
    run_phase_to_approval(orchestrator, project, reviewer_id=reviewer.id, task_request="Design the experience")
    run_phase_to_approval(
        orchestrator, project, reviewer_id=reviewer.id, task_request="Design the technical architecture"
    )
    assert project.current_phase == "data_integration"

    di_run = run_phase_to_approval(orchestrator, project, reviewer_id=reviewer.id, task_request="Design the data model")
    assert project.current_phase == "governance_security"
    assert project.phase_status == PhaseStatus.PENDING.value

    versions = db_session.query(ArtefactVersion).filter_by(run_id=di_run.id).all()
    assert len(versions) == 1
    version = versions[0]
    db_session.refresh(version)
    assert version.version_label == "v1.0"
    assert version.status == ArtefactVersionStatus.BASELINE.value

    doc = Document(version.file_path)
    full_text = "\n".join(p.text for p in doc.paragraphs)
    assert "DATA-001" in full_text
    assert "Contract and Approval Management" in full_text
