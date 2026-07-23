from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.agents_registry.registry import AgentRegistry
from app.api.deps import get_registry
from app.api.schemas import (
    AgentSummary,
    ArtefactVersionResponse,
    CreateProjectRequest,
    ProjectResponse,
    RunResponse,
    StartRunRequest,
    SubmitReviewRequest,
)
from app.db.session import get_session
from app.models.agent import AgentRun
from app.models.artefact import ArtefactVersion
from app.models.project import Project
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
