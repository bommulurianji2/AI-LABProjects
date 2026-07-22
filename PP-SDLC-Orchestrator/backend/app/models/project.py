import uuid
from datetime import UTC, datetime

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.domain.enums import LIFECYCLE_PHASES, PhaseStatus


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String(255))
    current_phase: Mapped[str] = mapped_column(String(50), default=LIFECYCLE_PHASES[0])
    phase_status: Mapped[str] = mapped_column(String(50), default=PhaseStatus.PENDING.value)
    status: Mapped[str] = mapped_column(String(50), default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC))
