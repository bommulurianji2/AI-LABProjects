"""Authoritative state machines for agent runs and project lifecycle phases.

Every transition must go through `transition_run` / `advance_phase` below —
these are the only functions allowed to change `AgentRun.state` or
`Project.phase` / `Project.phase_status`. This is what makes "progression is
blocked without approval" an enforced invariant rather than a UI convention.
"""

from dataclasses import dataclass

from app.domain.enums import LIFECYCLE_PHASES, PhaseStatus, ReviewDecision, RunState

RUN_TRANSITIONS: dict[RunState, frozenset[RunState]] = {
    RunState.NOT_STARTED: frozenset({RunState.READY}),
    RunState.READY: frozenset({RunState.QUEUED, RunState.CANCELLED}),
    RunState.QUEUED: frozenset({RunState.RUNNING, RunState.CANCELLED}),
    RunState.RUNNING: frozenset(
        {
            RunState.WAITING_FOR_CLARIFICATION,
            RunState.BLOCKED,
            RunState.READY_FOR_REVIEW,
            RunState.FAILED,
        }
    ),
    RunState.WAITING_FOR_CLARIFICATION: frozenset({RunState.RUNNING, RunState.CANCELLED}),
    RunState.BLOCKED: frozenset({RunState.READY, RunState.CANCELLED}),
    RunState.READY_FOR_REVIEW: frozenset({RunState.WAITING_FOR_HUMAN_REVIEW}),
    RunState.WAITING_FOR_HUMAN_REVIEW: frozenset({RunState.IN_REVIEW}),
    RunState.IN_REVIEW: frozenset(
        {
            RunState.APPROVED,
            RunState.APPROVED_WITH_COMMENTS,
            RunState.REWORK_REQUIRED,
            RunState.REJECTED,
        }
    ),
    RunState.APPROVED: frozenset({RunState.COMPLETED}),
    RunState.APPROVED_WITH_COMMENTS: frozenset({RunState.COMPLETED}),
    RunState.REWORK_REQUIRED: frozenset({RunState.READY}),
    RunState.REJECTED: frozenset({RunState.READY, RunState.CANCELLED}),
    RunState.FAILED: frozenset({RunState.READY, RunState.CANCELLED}),
    RunState.COMPLETED: frozenset(),
    RunState.CANCELLED: frozenset(),
}

# The IN_REVIEW -> {APPROVED, APPROVED_WITH_COMMENTS, REWORK_REQUIRED, REJECTED}
# edges require the caller to supply the human decision that authorizes them.
_REVIEW_GATED_TARGETS: dict[RunState, ReviewDecision] = {
    RunState.APPROVED: ReviewDecision.APPROVED,
    RunState.APPROVED_WITH_COMMENTS: ReviewDecision.APPROVED_WITH_COMMENTS,
    RunState.REWORK_REQUIRED: ReviewDecision.REWORK_REQUIRED,
    RunState.REJECTED: ReviewDecision.REJECTED,
}


class InvalidTransition(Exception):
    def __init__(self, current: RunState, target: RunState):
        super().__init__(f"Cannot transition run from {current.value!r} to {target.value!r}")
        self.current = current
        self.target = target


class ReviewGateError(Exception):
    """Raised when a review-gated transition is attempted without a matching decision."""


def transition_run(current: RunState, target: RunState, *, review_decision: ReviewDecision | None = None) -> RunState:
    """Validate and return the new run state, or raise.

    This function is pure (no DB access) so every edge is exhaustively
    unit-testable without a database.
    """
    allowed = RUN_TRANSITIONS.get(current, frozenset())
    if target not in allowed:
        raise InvalidTransition(current, target)

    required_decision = _REVIEW_GATED_TARGETS.get(target)
    if required_decision is not None and review_decision != required_decision:
        raise ReviewGateError(
            f"Transition to {target.value!r} requires review_decision={required_decision.value!r}, "
            f"got {review_decision!r}"
        )

    return target


@dataclass(frozen=True)
class PhaseAdvanceResult:
    phase: str
    phase_status: PhaseStatus
    project_completed: bool = False


def advance_phase(current_phase: str, current_status: PhaseStatus, *, decision: ReviewDecision) -> PhaseAdvanceResult:
    """Given the current phase/status and a human review decision on that
    phase's artefact, compute the next phase/status. Only APPROVED or
    APPROVED_WITH_COMMENTS unlock the next phase; REWORK_REQUIRED/REJECTED
    keep the project on the current phase in a rework-eligible state.
    """
    if current_status != PhaseStatus.AWAITING_REVIEW:
        raise ReviewGateError(
            f"Phase {current_phase!r} is {current_status.value!r}, not awaiting review — cannot apply a decision"
        )

    if decision in (ReviewDecision.APPROVED, ReviewDecision.APPROVED_WITH_COMMENTS):
        idx = LIFECYCLE_PHASES.index(current_phase)
        if idx == len(LIFECYCLE_PHASES) - 1:
            return PhaseAdvanceResult(phase=current_phase, phase_status=PhaseStatus.APPROVED, project_completed=True)
        next_phase = LIFECYCLE_PHASES[idx + 1]
        return PhaseAdvanceResult(phase=next_phase, phase_status=PhaseStatus.PENDING)

    if decision == ReviewDecision.REWORK_REQUIRED:
        return PhaseAdvanceResult(phase=current_phase, phase_status=PhaseStatus.REWORK)

    # REJECTED — stays on current phase, back to pending so a fresh run can be started.
    return PhaseAdvanceResult(phase=current_phase, phase_status=PhaseStatus.PENDING)
