from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.agents_registry.registry import AgentRegistry
from app.api.deps import get_registry
from app.api.schemas import (
    AgentSummary,
    ArtefactVersionResponse,
    CreateProjectRequest,
    CreateUserRequest,
    ProjectResponse,
    RunHistoryEntry,
    RunResponse,
    StartRunRequest,
    SubmitReviewRequest,
    UserResponse,
)
from app.db.session import get_session
from app.models.agent import AgentRun
from app.models.artefact import ArtefactVersion
from app.models.project import Project
from app.models.review import Review
from app.models.user import User
from app.orchestrator.service import OrchestrationError, OrchestratorService

router = APIRouter()

_DOWNLOAD_MEDIA_TYPES = {
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ".html": "text/html",
}


@router.get("/agents", response_model=list[AgentSummary])
def list_agents(registry: AgentRegistry = Depends(get_registry)):
    return [AgentSummary(**m.model_dump(include={"id", "display_name", "kind", "phase", "version"})) for m in registry.list_agents()]


@router.get("/users", response_model=list[UserResponse])
def list_users(session: Session = Depends(get_session)):
    return session.query(User).order_by(User.created_at.asc()).all()


@router.post("/users", response_model=UserResponse)
def create_user(body: CreateUserRequest, response: Response, session: Session = Depends(get_session)):
    """Get-or-create by email — reviewers are picked from a short internal
    list, not self-registered, so treating a repeat email as "the same
    reviewer" is friendlier than a 409 for this tool's actual usage pattern.
    """
    existing = session.query(User).filter_by(email=body.email).first()
    if existing is not None:
        response.status_code = 200
        return existing

    user = User(email=body.email, role=body.role)
    session.add(user)
    session.commit()
    response.status_code = 201
    return user


@router.post("/projects", response_model=ProjectResponse, status_code=201)
def create_project(
    body: CreateProjectRequest,
    session: Session = Depends(get_session),
    registry: AgentRegistry = Depends(get_registry),
):
    orchestrator = OrchestratorService(session=session, registry=registry)
    return orchestrator.create_project(body.name)


@router.get("/projects", response_model=list[ProjectResponse])
def list_projects(session: Session = Depends(get_session)):
    return session.query(Project).order_by(Project.created_at.desc()).all()


@router.get("/projects/{project_id}", response_model=ProjectResponse)
def get_project(project_id: str, session: Session = Depends(get_session)):
    project = session.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


@router.get("/projects/{project_id}/runs", response_model=list[RunHistoryEntry])
def list_project_runs(project_id: str, session: Session = Depends(get_session)):
    """Every run this project has ever had, across every phase — the
    run-history/audit view that was missing since session 1 (a page
    refresh mid-review previously lost track of the in-flight run
    entirely; the frontend now uses this to restore it).
    """
    project = session.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")

    runs = (
        session.query(AgentRun)
        .filter_by(project_id=project_id)
        .order_by(AgentRun.started_at.asc())
        .all()
    )

    entries = []
    for run in runs:
        versions = session.query(ArtefactVersion).filter_by(run_id=run.id).all()
        review_decision = None
        if versions:
            version_ids = [v.id for v in versions]
            latest_review = (
                session.query(Review)
                .filter(Review.artefact_version_id.in_(version_ids))
                .order_by(Review.decided_at.desc())
                .first()
            )
            if latest_review is not None:
                review_decision = latest_review.decision

        entries.append(
            RunHistoryEntry(
                id=run.id,
                project_id=run.project_id,
                agent_id=run.agent_id,
                phase=run.phase,
                run_number=run.run_number,
                state=run.state,
                started_at=run.started_at,
                ended_at=run.ended_at,
                review_decision=review_decision,
                artefact_types=[v.artefact_type for v in versions],
            )
        )
    return entries


@router.post("/projects/{project_id}/runs", response_model=RunResponse, status_code=201)
def start_run(
    project_id: str,
    body: StartRunRequest,
    session: Session = Depends(get_session),
    registry: AgentRegistry = Depends(get_registry),
):
    project = session.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")

    orchestrator = OrchestratorService(session=session, registry=registry)
    try:
        run = orchestrator.start_run(project, task_request=body.task_request, project_name_hint=project.name)
    except OrchestrationError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return run


@router.get("/runs/{run_id}", response_model=RunResponse)
def get_run(run_id: str, session: Session = Depends(get_session)):
    run = session.get(AgentRun, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    return run


@router.get("/runs/{run_id}/artefact-versions", response_model=list[ArtefactVersionResponse])
def list_run_artefact_versions(run_id: str, session: Session = Depends(get_session)):
    """Every artefact version this run produced — a run can produce more
    than one (e.g. the UX Design Agent's spec + prototype), so callers must
    not assume there's exactly one.
    """
    return (
        session.query(ArtefactVersion)
        .filter_by(run_id=run_id)
        .order_by(ArtefactVersion.created_at.asc())
        .all()
    )


@router.get("/artefact-versions/{version_id}/download")
def download_artefact_version(version_id: str, session: Session = Depends(get_session)):
    version = session.get(ArtefactVersion, version_id)
    if version is None:
        raise HTTPException(status_code=404, detail="Artefact version not found")

    file_path = Path(version.file_path)
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Artefact file no longer exists on disk")

    media_type = _DOWNLOAD_MEDIA_TYPES.get(file_path.suffix.lower(), "application/octet-stream")
    return FileResponse(path=file_path, media_type=media_type, filename=f"{version.version_label}{file_path.suffix}")


@router.post("/runs/{run_id}/review", response_model=ProjectResponse)
def submit_review(
    run_id: str,
    body: SubmitReviewRequest,
    session: Session = Depends(get_session),
    registry: AgentRegistry = Depends(get_registry),
):
    run = session.get(AgentRun, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")

    orchestrator = OrchestratorService(session=session, registry=registry)
    try:
        project = orchestrator.submit_review(
            run, reviewer_id=body.reviewer_id, decision=body.decision, comments=body.comments
        )
    except OrchestrationError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return project
