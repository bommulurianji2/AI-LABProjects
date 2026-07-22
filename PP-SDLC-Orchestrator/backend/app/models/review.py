import uuid
from datetime import UTC, datetime

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Review(Base):
    __tablename__ = "reviews"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    artefact_version_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("artefact_versions.id"), index=True
    )
    reviewer_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"))
    decision: Mapped[str] = mapped_column(String(30))  # ReviewDecision value
    decided_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC))


class ReviewComment(Base):
    __tablename__ = "review_comments"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    review_id: Mapped[str] = mapped_column(String(36), ForeignKey("reviews.id"), index=True)
    body: Mapped[str] = mapped_column(Text)
    entity_ref: Mapped[str | None] = mapped_column(String(100), nullable=True)  # e.g. "REQ-001"
