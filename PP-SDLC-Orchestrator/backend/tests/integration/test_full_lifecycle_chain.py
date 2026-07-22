"""The capstone test: drives all 10 specialist agents end-to-end,
Analysis through Hypercare & Closure, and confirms the project's overall
status becomes `completed` only after the final phase is approved — not
before. Also confirms all 10 agents (and no more, no fewer) are registered
with zero validation failures.
"""

from app.agents_registry.registry import AgentRegistry
from app.domain.enums import PhaseStatus
from app.models.user import User
from tests.helpers import make_orchestrator, run_phase_to_approval

EXPECTED_AGENT_IDS = {
    "analysis",
    "ux_design",
    "technical_design",
    "data_integration",
    "governance_security",
    "build",
    "validation_qa",
    "test",
    "deploy",
    "hypercare_closure",
}


def test_all_ten_specialist_agents_are_registered():
    reg = AgentRegistry()
    reg.load()
    assert reg.failures == [], f"unexpected registration failures: {reg.failures}"
    assert {m.id for m in reg.list_agents()} == EXPECTED_AGENT_IDS


def test_full_lifecycle_completes_only_after_final_phase_approved(db_session):
    orchestrator = make_orchestrator(db_session)
    reviewer = User(email="project.owner@example.test", role="Project Owner")
    db_session.add(reviewer)
    db_session.commit()

    project = orchestrator.create_project("Employee Leave Request")

    task_requests_by_phase = {
        "analysis": "Draft requirements",
        "ux_design": "Design the experience",
        "technical_design": "Design the technical architecture",
        "data_integration": "Design the data model",
        "governance_security": "Define governance and security controls",
        "build": "Build the solution",
        "validation_qa": "Independently validate the build",
        "test": "Execute test cases",
        "deploy": "Deploy the solution",
    }

    for phase, task_request in task_requests_by_phase.items():
        assert project.current_phase == phase, f"expected to be on {phase}, was on {project.current_phase}"
        run_phase_to_approval(orchestrator, project, reviewer_id=reviewer.id, task_request=task_request)
        assert project.status != "completed", "project must not complete before the final phase is approved"

    # Now on the final phase - project must still be "active" until this is approved too.
    assert project.current_phase == "hypercare_closure"
    assert project.status == "active"

    final_run = orchestrator.start_run(project, task_request="Run hypercare and close the project")
    assert project.status == "active", "must not complete merely from starting the final run"

    from app.domain.enums import ReviewDecision

    final_project = orchestrator.submit_review(final_run, reviewer_id=reviewer.id, decision=ReviewDecision.APPROVED)

    assert final_project.status == "completed"
    assert final_project.current_phase == "hypercare_closure"
    assert final_project.phase_status == PhaseStatus.APPROVED.value
