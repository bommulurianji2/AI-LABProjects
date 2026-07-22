"""The common agent input/output envelope — see 03_Agent_Skills/AGENT_CONTRACT.md.

Both the mock runtime and any future LLM runtime return the same
`AgentRunResult` shape, which is what lets a manifest swap `runtime: mock`
for `runtime: llm` without orchestration code ever branching on it.
"""

from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass
class SourceArtefactRef:
    artefact_id: str
    version_id: str
    version_label: str


@dataclass
class AgentRunRequest:
    execution_mode: str  # "orchestrated" | "standalone"
    project_id: str
    invocation_id: str
    agent_id: str
    task_id: str
    task_request: str
    lifecycle_phase: str | None
    source_artefacts: list[SourceArtefactRef] = field(default_factory=list)
    reference_documents: list[str] = field(default_factory=list)
    constraints: dict[str, Any] = field(default_factory=dict)
    requested_outputs: list[str] = field(default_factory=list)
    output_path: str | None = None
    previous_output: str | None = None
    previous_version: str | None = None
    reviewer_comments: list[str] = field(default_factory=list)
    rework_context: dict[str, Any] | None = None
    open_clarifications: list[str] = field(default_factory=list)
    accepted_assumptions: list[str] = field(default_factory=list)
    security_context: dict[str, Any] = field(default_factory=dict)
    user_identity: str | None = None
    correlation_id: str | None = None
    run_number: int = 1


@dataclass
class ProducedArtefact:
    artefact_type: str
    stable_key: str
    file_path: str
    checksum: str
    entities: list[str] = field(default_factory=list)  # e.g. ["REQ-001", "REQ-002"]


@dataclass
class AgentRunResult:
    execution_summary: str
    artefacts_produced: list[ProducedArtefact] = field(default_factory=list)
    references_used: list[str] = field(default_factory=list)
    assumptions: list[str] = field(default_factory=list)
    clarifications: list[str] = field(default_factory=list)
    risks: list[str] = field(default_factory=list)
    decisions: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    validation_findings: list[str] = field(default_factory=list)
    handoff_package: dict[str, Any] = field(default_factory=dict)
    rework_recommendations: list[str] = field(default_factory=list)
    downstream_impacts: list[str] = field(default_factory=list)
    review_status: str = "ready_for_review"
    execution_metrics: dict[str, Any] = field(default_factory=dict)
    error: str | None = None


class AgentAdapter(Protocol):
    """Every specialist agent's runtime implements this — mock today, LLM later."""

    def execute(self, request: AgentRunRequest) -> AgentRunResult: ...
