import uuid
from datetime import UTC, datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.domain.enums import RunState


class AgentDef(Base):
    """Mirrors a validated agent manifest — a cached row for FK integrity."""

    __tablename__ = "agent_defs"

    id: Mapped[str] = mapped_column(String(100), primary_key=True)  # manifest `id`, e.g. "analysis"
    kind: Mapped[str] = mapped_column(String(20))  # orchestrator | specialist
    phase: Mapped[str | None] = mapped_column(String(50), nullable=True)
    version: Mapped[str] = mapped_column(String(20))
    display_name: Mapped[str] = mapped_column(String(255))


class AgentRun(Base):
    __tablename__ = "agent_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id: Mapped[str] = mapped_column(String(36), ForeignKey("projects.id"), index=True)
    agent_id: Mapped[str] = mapped_column(String(100), ForeignKey("agent_defs.id"))
    phase: Mapped[str] = mapped_column(String(50))
    run_number: Mapped[int] = mapped_column(Integer, default=1)
    state: Mapped[str] = mapped_column(String(50), default=RunState.NOT_STARTED.value)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    input_snapshot_ref: Mapped[str | None] = mapped_column(String(500), nullable=True)


class RunEvent(Base):
    """Append-only audit log for a run — the structured substitute for chat history."""

    __tablename__ = "run_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    run_id: Mapped[str] = mapped_column(String(36), ForeignKey("agent_runs.id"), index=True)
    ts: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC))
    type: Mapped[str] = mapped_column(String(100))
    payload_json: Mapped[str] = mapped_column(Text, default="{}")
