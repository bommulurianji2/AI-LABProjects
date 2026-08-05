"""Deterministic stand-in for a real ModelProvider.

Used by the autouse `stub_model_provider` fixture (see tests/conftest.py)
so the full test suite runs `runtime: llm` agents with zero network calls
and zero cost. Also usable directly for adapter-level unit tests that need
to control the exact response.
"""

import json


class FakeModelProvider:
    def __init__(self, response_text: str | None = None):
        self._response_text = response_text or json.dumps(
            {
                "scope": "Fake-provider scope for automated tests.",
                "functional_requirements": [
                    "The system shall allow an authenticated user to create a new project.",
                    "The system shall capture a high-level requirement document per project.",
                    "The system shall record functional and non-functional requirements distinctly.",
                ],
                "assumptions": ["No blocking assumptions for this fake-provider test run."],
            }
        )
        self.calls: list[dict[str, str]] = []

    def complete(self, *, system: str, user: str) -> str:
        self.calls.append({"system": system, "user": user})
        return self._response_text
