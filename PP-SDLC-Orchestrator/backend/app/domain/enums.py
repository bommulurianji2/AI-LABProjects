from enum import StrEnum


class RunState(StrEnum):
    NOT_STARTED = "not_started"
    READY = "ready"
    QUEUED = "queued"
    RUNNING = "running"
    WAITING_FOR_CLARIFICATION = "waiting_for_clarification"
    WAITING_FOR_HUMAN_REVIEW = "waiting_for_human_review"
    BLOCKED = "blocked"
    READY_FOR_REVIEW = "ready_for_review"
    IN_REVIEW = "in_review"
    APPROVED = "approved"
    APPROVED_WITH_COMMENTS = "approved_with_comments"
    REWORK_REQUIRED = "rework_required"
    REJECTED = "rejected"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class PhaseStatus(StrEnum):
    PENDING = "pending"
    ACTIVE = "active"
    AWAITING_REVIEW = "awaiting_review"
    APPROVED = "approved"
    REWORK = "rework"


class ReviewDecision(StrEnum):
    APPROVED = "approved"
    APPROVED_WITH_COMMENTS = "approved_with_comments"
    REWORK_REQUIRED = "rework_required"
    REJECTED = "rejected"


class ArtefactVersionStatus(StrEnum):
    DRAFT = "draft"
    BASELINE = "baseline"
    SUPERSEDED = "superseded"


class InputSufficiency(StrEnum):
    SUFFICIENT = "sufficient"
    CONDITIONALLY_SUFFICIENT = "conditionally_sufficient"
    INSUFFICIENT = "insufficient"


# Fixed lifecycle phase order — session 1 only drives ANALYSIS end-to-end;
# the rest stay PENDING until their agent is implemented.
LIFECYCLE_PHASES: list[str] = [
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
]
