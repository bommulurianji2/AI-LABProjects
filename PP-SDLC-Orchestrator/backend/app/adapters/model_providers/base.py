"""The provider-agnostic interface every LLM-backed agent adapter talks to.

Keeping this Protocol tiny (one method) is what lets an agent's manifest
swap `runtime: mock` for `runtime: llm`, or swap OpenRouter for a future
Azure OpenAI/Foundry provider, without touching orchestration code or the
adapter's prompt/parsing logic.
"""

from typing import Protocol


class ModelProvider(Protocol):
    def complete(self, *, system: str, user: str) -> str:
        """Return the model's raw text completion for a system+user prompt pair."""
        ...


class ModelProviderError(Exception):
    """Raised when a model call fails, times out, or returns something unusable.

    Adapters let this propagate — OrchestratorService.start_run already
    catches any adapter exception, marks the run FAILED, and surfaces a
    clear error rather than fabricating a successful result.
    """
