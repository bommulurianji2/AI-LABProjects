"""Shared test helpers for driving the orchestrated loop across multiple
phases without re-deriving the same create/run/review boilerplate in every
chain test.
"""

from app.agents_registry.registry import AgentRegistry
from app.domain.enums import ReviewDecision
from app.orchestrator.service import OrchestratorService, sync_agent_defs


def make_orchestrator(session) -> OrchestratorService:
    registry = AgentRegistry()
    registry.load()  # real 03_Agent_Skills dir
    assert registry.failures == [], f"registry failures: {registry.failures}"
    sync_agent_defs(session, registry.list_agents())
    return OrchestratorService(session, registry)


def run_phase_to_approval(orchestrator, project, *, reviewer_id: str, task_request: str):
    """Starts a run for the project's current phase and immediately approves
    it. Returns the run so callers can inspect its produced artefacts.
    """
    run = orchestrator.start_run(project, task_request=task_request)
    orchestrator.submit_review(run, reviewer_id=reviewer_id, decision=ReviewDecision.APPROVED)
    return run
