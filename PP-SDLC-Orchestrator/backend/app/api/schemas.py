from datetime import datetime

from pydantic import BaseModel

from app.domain.enums import ReviewDecision


class CreateProjectRequest(BaseModel):
    name: str


class ProjectResponse(BaseModel):
    id: str
    name: str
    current_phase: str
    phase_status: str
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}


class StartRunRequest(BaseModel):
    task_request: str


class RunResponse(BaseModel):
    id: str
    project_id: str
    agent_id: str
    phase: str
    run_number: int
    state: str

    model_config = {"from_attributes": True}


class ArtefactVersionResponse(BaseModel):
    id: str
    artefact_id: str
    artefact_type: str
    version_label: str
    file_path: str
    checksum: str
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}


class SubmitReviewRequest(BaseModel):
    reviewer_id: str
    decision: ReviewDecision
    comments: list[str] = []


class AgentSummary(BaseModel):
    id: str
    display_name: str
    kind: str
    phase: str | None
    version: str
