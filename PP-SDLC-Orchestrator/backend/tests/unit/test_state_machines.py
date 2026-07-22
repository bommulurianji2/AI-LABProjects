import pytest

from app.domain.enums import PhaseStatus, ReviewDecision, RunState
from app.orchestrator.state_machines import (
    RUN_TRANSITIONS,
    InvalidTransition,
    ReviewGateError,
    advance_phase,
    transition_run,
)

ALL_STATES = list(RunState)


def _allowed_pairs():
    for current, targets in RUN_TRANSITIONS.items():
        for target in targets:
            yield current, target


def _blocked_pairs():
    for current in ALL_STATES:
        allowed = RUN_TRANSITIONS.get(current, frozenset())
        for target in ALL_STATES:
            if target not in allowed:
                yield current, target


REVIEW_DECISION_FOR_TARGET = {
    RunState.APPROVED: ReviewDecision.APPROVED,
    RunState.APPROVED_WITH_COMMENTS: ReviewDecision.APPROVED_WITH_COMMENTS,
    RunState.REWORK_REQUIRED: ReviewDecision.REWORK_REQUIRED,
    RunState.REJECTED: ReviewDecision.REJECTED,
}


@pytest.mark.parametrize("current,target", list(_allowed_pairs()))
def test_allowed_transition_succeeds(current, target):
    decision = REVIEW_DECISION_FOR_TARGET.get(target)
    assert transition_run(current, target, review_decision=decision) == target


@pytest.mark.parametrize("current,target", list(_blocked_pairs()))
def test_blocked_transition_raises(current, target):
    with pytest.raises(InvalidTransition):
        transition_run(current, target)


def test_review_gated_transition_without_decision_raises():
    with pytest.raises(ReviewGateError):
        transition_run(RunState.IN_REVIEW, RunState.APPROVED)


def test_review_gated_transition_with_wrong_decision_raises():
    with pytest.raises(ReviewGateError):
        transition_run(RunState.IN_REVIEW, RunState.APPROVED, review_decision=ReviewDecision.REJECTED)


def test_every_run_state_has_a_transition_table_entry():
    # Guards against silently adding a new RunState without wiring its edges.
    for state in ALL_STATES:
        assert state in RUN_TRANSITIONS


def test_advance_phase_approved_unlocks_next_phase():
    result = advance_phase("analysis", PhaseStatus.AWAITING_REVIEW, decision=ReviewDecision.APPROVED)
    assert result.phase == "ux_design"
    assert result.phase_status == PhaseStatus.PENDING
    assert result.project_completed is False


def test_advance_phase_approved_with_comments_also_unlocks():
    result = advance_phase("analysis", PhaseStatus.AWAITING_REVIEW, decision=ReviewDecision.APPROVED_WITH_COMMENTS)
    assert result.phase == "ux_design"


def test_advance_phase_rework_required_stays_on_phase():
    result = advance_phase("analysis", PhaseStatus.AWAITING_REVIEW, decision=ReviewDecision.REWORK_REQUIRED)
    assert result.phase == "analysis"
    assert result.phase_status == PhaseStatus.REWORK


def test_advance_phase_rejected_stays_on_phase_pending():
    result = advance_phase("analysis", PhaseStatus.AWAITING_REVIEW, decision=ReviewDecision.REJECTED)
    assert result.phase == "analysis"
    assert result.phase_status == PhaseStatus.PENDING


def test_advance_phase_last_phase_completes_project():
    result = advance_phase("hypercare_closure", PhaseStatus.AWAITING_REVIEW, decision=ReviewDecision.APPROVED)
    assert result.project_completed is True


def test_advance_phase_requires_awaiting_review_status():
    with pytest.raises(ReviewGateError):
        advance_phase("analysis", PhaseStatus.ACTIVE, decision=ReviewDecision.APPROVED)
