"""Extends the chain to a ninth real agent: ... -> Test -> Deploy. Confirms
the IQ Document is generated referencing the zero-defect pre-deployment
check, and approval unlocks hypercare_closure.
"""

from docx import Document

from app.domain.enums import ArtefactVersionStatus, PhaseStatus
from app.models.artefact import ArtefactVersion
from app.models.user import User
from tests.helpers import make_orchestrator, run_phase_to_approval


def test_chain_through_deploy_unlocks_hypercare_closure(db_session):
    orchestrator = make_orchestrator(db_session)
    reviewer = User(email="deployment.manager@example.test", role="Reviewer")
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
    run_phase_to_approval(
        orchestrator, project, reviewer_id=reviewer.id, task_request="Independently validate the build"
    )
    run_phase_to_approval(orchestrator, project, reviewer_id=reviewer.id, task_request="Execute test cases")
    assert project.current_phase == "deploy"

    deploy_run = run_phase_to_approval(orchestrator, project, reviewer_id=reviewer.id, task_request="Deploy the solution")
    assert project.current_phase == "hypercare_closure"
    assert project.phase_status == PhaseStatus.PENDING.value

    versions = db_session.query(ArtefactVersion).filter_by(run_id=deploy_run.id).all()
    assert len(versions) == 1
    version = versions[0]
    db_session.refresh(version)
    assert version.version_label == "v1.0"
    assert version.status == ArtefactVersionStatus.BASELINE.value

    doc = Document(version.file_path)
    full_text = "\n".join(p.text for p in doc.paragraphs)
    assert "zero open defects" in full_text
