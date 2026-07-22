"""Import every model module so Base.metadata is fully populated for Alembic autogenerate."""

from app.models.agent import AgentDef, AgentRun, RunEvent
from app.models.artefact import Artefact, ArtefactVersion
from app.models.project import Project
from app.models.review import Review, ReviewComment
from app.models.user import User

__all__ = [
    "AgentDef",
    "AgentRun",
    "RunEvent",
    "Artefact",
    "ArtefactVersion",
    "Project",
    "Review",
    "ReviewComment",
    "User",
]
