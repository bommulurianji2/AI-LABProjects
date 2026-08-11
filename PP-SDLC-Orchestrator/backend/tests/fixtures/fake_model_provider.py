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
        # Technical Design
        "options": [
            {"name": "Model-driven app on Dataverse", "tradeoff": "Faster to build, less UI flexibility."},
            {"name": "Canvas app on Dataverse", "tradeoff": "Full UI control, more build effort."},
        ],
        "architecture_decisions": [
            "Use Dataverse as the system of record for all request data.",
            "Use Power Automate for all cross-entity workflow orchestration.",
            "Expose external system access only through custom connectors.",
        ],
        "risks": ["Dataverse API limits may throttle bulk operations during peak submission periods."],
        "limitations": ["Offline mobile support is out of scope for the initial release."],
        "dependencies": ["Requires a Dataverse environment provisioned before the Build phase starts."],
        "logical_architecture": (
            "Power Platform canvas/model-driven app frontend, Dataverse as the system of record, "
            "Power Automate for workflow orchestration."
        ),
        "integration_overview": (
            "External systems are integrated via dedicated custom connectors; no direct HTTP calls "
            "from flows to third-party APIs."
        ),
        "infrastructure_overview": (
            "Dev/test/prod Power Platform environments with solution-based ALM."
        ),
        # Data & Integration
        "entities": [
            {"name": "Facility", "description": "A bookable room or desk with capacity and amenities."},
            {"name": "Booking", "description": "A reservation of a Facility by an Employee for a time slot."},
        ],
        "relationships": ["Booking N:1 Facility", "Booking N:1 Employee"],
        "external_sources": ["Azure Active Directory maps to the Employee table via object ID."],
        "connectors": ["Office 365 Outlook connector for calendar invitations."],
        "data_migration": "No legacy data migration is required for the initial release.",
        "reporting_model": "Power BI reporting is deferred until reporting requirements are confirmed.",
        # Governance & Security
        "identity_design": "Microsoft Entra ID as the identity provider; delegated permissions by default.",
        "permissions": "Least privilege: delegated Graph permissions unless justified otherwise.",
        "environment_strategy": "Separate dev, test, and production Power Platform environments.",
        "dlp": [
            "Business data group: Dataverse, SharePoint, Microsoft Teams.",
            "Non-business data group: all other connectors, blocked by default.",
        ],
        "connector_governance": "Every connector introduced upstream requires an explicit DLP classification.",
        "licensing": ["Microsoft 365 E3 or E5 licenses required for all end users."],
        "compliance": "No regulated data categories identified for this fake-provider test run.",
        "operational_ownership": "Platform Administrator owns environment health; Project Owner owns escalation.",
        "audit_requirements": "All approval and rework events are captured in the audit log.",
    }


class FakeModelProvider:
    def __init__(self, response_text: str | None = None):
        self._response_text = response_text or json.dumps(_default_response())
        self.calls: list[dict[str, str]] = []

    def complete(self, *, system: str, user: str) -> str:
        self.calls.append({"system": system, "user": user})
        return self._response_text
