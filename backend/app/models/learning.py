"""Lesson progress database model.

Tracks per-user learning progress for lessons identified by their stable
content-layer slug. Since M26 the authoritative lesson content lives in
PostgreSQL (see ``app/models/content.py``); ``app/learning/content.py`` is the
seed source that populates the database. This table persists only a user's
progress.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, generate_uuid


class LessonProgress(Base, TimestampMixin):
    """A user's progress through one lesson."""

    __tablename__ = "lesson_progress"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=generate_uuid,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    lesson_slug: Mapped[str] = mapped_column(String(100), nullable=False)
    completed_sections: Mapped[list[str]] = mapped_column(
        JSON,
        nullable=False,
        default=list,
        comment="Ids of completed sections, in completion order",
    )
    answers: Mapped[dict[str, bool]] = mapped_column(
        JSON,
        nullable=False,
        default=dict,
        comment="question_id -> whether the user's submission was correct",
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="When every section of the lesson was completed",
    )

    __table_args__ = (
        UniqueConstraint("user_id", "lesson_slug", name="uq_progress_user_lesson"),
    )

    def __repr__(self) -> str:
        """Return string representation without sensitive data."""
        return (
            f"<LessonProgress user_id={self.user_id} "
            f"lesson_slug={self.lesson_slug}>"
        )
