"""OrchestratorService — the deterministic domain service that owns project
state, version numbers, and approval gating. Specialist agents never write
DB state directly; only this service does, via the state machines in
`state_machines.py`.
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.agents_registry.contract import AgentRunRequest
from app.agents_registry.manifest_schema import AgentManifest
from app.agents_registry.registry import AgentRegistry
from app.domain.enums import ArtefactVersionStatus, PhaseStatus, ReviewDecision, RunState
from app.models.agent import AgentDef, AgentRun, RunEvent
from app.models.artefact import Artefact, ArtefactVersion
from app.models.project import Project
from app.models.review import Review, ReviewComment
from app.orchestrator.state_machines import advance_phase, transition_run


class OrchestrationError(Exception):
    pass


def sync_agent_defs(session: Session, manifests: list[AgentManifest]) -> None:
    """Upsert AgentDef rows so AgentRun.agent_id has a valid FK target."""
    existing = {a.id: a for a in session.query(AgentDef).all()}
    for m in manifests:
        if m.id in existing:
            row = existing[m.id]
            row.kind, row.phase, row.version, row.display_name = m.kind, m.phase, m.version, m.display_name
        else:
            session.add(
                AgentDef(id=m.id, kind=m.kind, phase=m.phase, version=m.version, display_name=m.display_name)
            )
    session.commit()


class OrchestratorService:
    def __init__(self, session: Session, registry: AgentRegistry):
        self.session = session
        self.registry = registry

    def create_project(self, name: str) -> Project:
        from app.domain.enums import LIFECYCLE_PHASES

        project = Project(name=name, current_phase=LIFECYCLE_PHASES[0], phase_status=PhaseStatus.PENDING.value)
        self.session.add(project)
        self.session.commit()
        return project

    def _log_event(self, run: AgentRun, event_type: str, payload: str = "{}") -> None:
        self.session.add(RunEvent(run_id=run.id, ts=datetime.now(UTC), type=event_type, payload_json=payload))

    def start_run(self, project: Project, *, task_request: str, project_name_hint: str | None = None) -> AgentRun:
        """Runs the current phase's agent to completion of the mock work and
        parks the run at WAITING_FOR_HUMAN_REVIEW, awaiting `submit_review`.
        """
        entry = self.registry.get_agent(project.current_phase)
        if entry is None:
            raise OrchestrationError(f"No registered agent for phase {project.current_phase!r}")

        if project.phase_status not in (PhaseStatus.PENDING.value, PhaseStatus.REWORK.value):
            raise OrchestrationError(
                f"Phase {project.current_phase!r} is {project.phase_status!r}; cannot start a new run"
            )

        prior_runs = (
            self.session.query(AgentRun)
            .filter_by(project_id=project.id, phase=project.current_phase)
            .count()
        )
        run_number = prior_runs + 1

        run = AgentRun(
            project_id=project.id,
            agent_id=entry.manifest.id,
            phase=project.current_phase,
            run_number=run_number,
            state=RunState.NOT_STARTED.value,
        )
        self.session.add(run)
        self.session.commit()

        run.state = transition_run(RunState.NOT_STARTED, RunState.READY).value
        run.state = transition_run(RunState.READY, RunState.QUEUED).value
        run.state = transition_run(RunState.QUEUED, RunState.RUNNING).value
        run.started_at = datetime.now(UTC)
        self._log_event(run, "run_started")
        self.session.commit()

        adapter = entry.adapter_class()
        request = AgentRunRequest(
            execution_mode="orchestrated",
            project_id=project.id,
            invocation_id=str(uuid.uuid4()),
            agent_id=entry.manifest.id,
            task_id=str(uuid.uuid4()),
            task_request=task_request,
            lifecycle_phase=project.current_phase,
            constraints={"project_name": project_name_hint or project.name},
            run_number=run_number,
        )

        try:
            result = adapter.execute(request)
        except Exception as exc:  # adapter failure -> run FAILED, not a crash
            run.state = transition_run(RunState.RUNNING, RunState.FAILED).value
            run.ended_at = datetime.now(UTC)
            self._log_event(run, "run_failed", f'{{"error": "{exc}"}}')
            self.session.commit()
            raise OrchestrationError(f"Agent execution failed: {exc}") from exc

        run.state = transition_run(RunState.RUNNING, RunState.READY_FOR_REVIEW).value
        self._log_event(run, "run_ready_for_review")
        self.session.commit()

        for produced in result.artefacts_produced:
            artefact = (
                self.session.query(Artefact)
                .filter_by(project_id=project.id, artefact_type=produced.artefact_type, stable_key=produced.stable_key)
                .one_or_none()
            )
            if artefact is None:
                artefact = Artefact(
                    project_id=project.id,
                    phase=project.current_phase,
                    artefact_type=produced.artefact_type,
                    stable_key=produced.stable_key,
                )
                self.session.add(artefact)
                self.session.commit()

            version_label = "v0.1" if run_number == 1 else f"v0.{run_number}"
            artefact_version = ArtefactVersion(
                artefact_id=artefact.id,
                version_label=version_label,
                run_id=run.id,
                file_path=produced.file_path,
                checksum=produced.checksum,
                status=ArtefactVersionStatus.DRAFT.value,
            )
            self.session.add(artefact_version)

        run.state = transition_run(RunState.READY_FOR_REVIEW, RunState.WAITING_FOR_HUMAN_REVIEW).value
        run.ended_at = datetime.now(UTC)
        self._log_event(run, "run_waiting_for_human_review")

        project.phase_status = PhaseStatus.AWAITING_REVIEW.value
        self.session.commit()

        return run

    def submit_review(
        self, run: AgentRun, *, reviewer_id: str, decision: ReviewDecision, comments: list[str] | None = None
    ) -> Project:
        if run.state != RunState.WAITING_FOR_HUMAN_REVIEW.value:
            raise OrchestrationError(f"Run is {run.state!r}, not waiting for human review")

        run.state = transition_run(RunState.WAITING_FOR_HUMAN_REVIEW, RunState.IN_REVIEW).value
        self._log_event(run, "review_opened")
        self.session.commit()

        target = {
            ReviewDecision.APPROVED: RunState.APPROVED,
            ReviewDecision.APPROVED_WITH_COMMENTS: RunState.APPROVED_WITH_COMMENTS,
            ReviewDecision.REWORK_REQUIRED: RunState.REWORK_REQUIRED,
            ReviewDecision.REJECTED: RunState.REJECTED,
        }[decision]
        run.state = transition_run(RunState.IN_REVIEW, target, review_decision=decision).value

        # A run can produce more than one artefact (e.g. the UX Design Agent's
        # spec + prototype) — every version this run produced gets its own
        # Review row and, on approval, is promoted, not just the most recent.
        versions_from_run = (
            self.session.query(ArtefactVersion)
            .filter_by(run_id=run.id)
            .order_by(ArtefactVersion.created_at.asc())
            .all()
        )
        for version in versions_from_run:
            review = Review(artefact_version_id=version.id, reviewer_id=reviewer_id, decision=decision.value)
            self.session.add(review)
            self.session.commit()
            for comment in comments or []:
                self.session.add(ReviewComment(review_id=review.id, body=comment))

            if decision in (ReviewDecision.APPROVED, ReviewDecision.APPROVED_WITH_COMMENTS):
                # Session-1 scope: promote the first approved draft directly to the
                # v1.0 baseline in place. Multi-cycle baseline history (v1.1, v2.0
                # via copy-on-approve) is deferred — see implementation ledger.
                version.status = ArtefactVersionStatus.BASELINE.value
                version.version_label = "v1.0"

        self._log_event(run, "review_decided", f'{{"decision": "{decision.value}"}}')

        if target in (RunState.APPROVED, RunState.APPROVED_WITH_COMMENTS):
            run.state = transition_run(target, RunState.COMPLETED).value
            run.ended_at = datetime.now(UTC)

        project = self.session.query(Project).filter_by(id=run.project_id).one()
        result = advance_phase(project.current_phase, PhaseStatus(project.phase_status), decision=decision)
        project.current_phase = result.phase
        project.phase_status = result.phase_status.value
        if result.project_completed:
            project.status = "completed"

        self.session.commit()
        return project
