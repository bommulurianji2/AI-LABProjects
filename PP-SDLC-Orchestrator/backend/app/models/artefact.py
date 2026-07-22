import uuid
from datetime import UTC, datetime

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.domain.enums import ArtefactVersionStatus


class Artefact(Base):
    """The logical artefact (e.g. 'Requirement Specification for Project X') — versions hang off this."""

    __tablename__ = "artefacts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id: Mapped[str] = mapped_column(String(36), ForeignKey("projects.id"), index=True)
    phase: Mapped[str] = mapped_column(String(50))
    artefact_type: Mapped[str] = mapped_column(String(100))
    # Semantic slug set once, carried across every version of this artefact.
    # NEVER derive from array position/order — that is what lets stable IDs
    # survive reruns per the versioning requirement.
    stable_key: Mapped[str] = mapped_column(String(200))


class ArtefactVersion(Base):
    __tablename__ = "artefact_versions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    artefact_id: Mapped[str] = mapped_column(String(36), ForeignKey("artefacts.id"), index=True)
    version_label: Mapped[str] = mapped_column(String(20))  # v0.1, v1.0, v1.1, v2.0 ...
    run_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("agent_runs.id"), nullable=True)
    file_path: Mapped[str] = mapped_column(String(500))
    checksum: Mapped[str] = mapped_column(String(64))  # sha256 hex digest
    status: Mapped[str] = mapped_column(String(20), default=ArtefactVersionStatus.DRAFT.value)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC))
