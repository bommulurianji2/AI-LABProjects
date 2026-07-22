"""A minimal valid AgentAdapter used only by registry unit tests."""

from app.agents_registry.contract import AgentRunRequest, AgentRunResult


class DummyAdapter:
    def execute(self, request: AgentRunRequest) -> AgentRunResult:
        return AgentRunResult(execution_summary="dummy")


class AdapterWithoutExecute:
    """Deliberately missing execute() — used to test rejection."""
