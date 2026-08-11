"""Deterministic stand-in for a real ModelProvider.

Used by the autouse `stub_model_provider` fixture (see tests/conftest.py)
so the full test suite runs `runtime: llm` agents with zero network calls
and zero cost. Also usable directly for adapter-level unit tests that need
to control the exact response.
"""

import json


def _default_response() -> dict:
    """A superset response covering every LLM adapter's schema so far — as
    each new agent gets a `runtime: llm` adapter with its own required
    keys, add them here rather than teaching this class per-agent
    detection logic. Every adapter just reads the keys it cares about and
    ignores the rest.
    """
    return {
        # Analysis
        "scope": "Fake-provider scope for automated tests.",
        "functional_requirements": [
            "The system shall allow an authenticated user to create a new project.",
            "The system shall capture a high-level requirement document per project.",
            "The system shall record functional and non-functional requirements distinctly.",
        ],
        "assumptions": ["No blocking assumptions for this fake-provider test run."],
        # UX Design
        "personas": [
            "Priya, an HR administrator who processes requests in bulk.",
            "Sam, a first-time employee user who needs a simple, guided flow.",
        ],
        "journeys": [
            "Submit a new request, receive confirmation, and track its status to resolution.",
            "Review a pending request and approve or reject it.",
        ],
        "screens": [
            {"name": "Dashboard", "description": "Landing screen summarizing open items."},
            {"name": "Request Form", "description": "Guided form for submitting a new request."},
            {"name": "Approvals Queue", "description": "List of items awaiting the current user's decision."},
        ],
        "navigation": "Top-level tabs for Dashboard, Requests, and Approvals.",
        "responsive_behavior": "Layouts collapse to a single column below 768px.",
        "accessibility": "All interactive elements are keyboard-reachable with WCAG AA contrast.",
    }


class FakeModelProvider:
    def __init__(self, response_text: str | None = None):
        self._response_text = response_text or json.dumps(_default_response())
        self.calls: list[dict[str, str]] = []

    def complete(self, *, system: str, user: str) -> str:
        self.calls.append({"system": system, "user": user})
        return self._response_text
