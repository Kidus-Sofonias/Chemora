"""Educational content database models (M26).

CONTENT vs CHEMISTRY boundary (mandatory):

- This module stores *educational content* only — lesson metadata, sections,
  prose, question prompts, options, explanations, ordering, and publication
  state.
- It stores **chemistry references** (an element symbol or a molecule input),
  never computed chemistry values. Values are resolved live by ChemEngine
  through the existing element/chemistry APIs, so the engine stays the only
  source of chemical truth.
- The answer key (``correct``) is stored here but is never serialized to
  student endpoints; only the admin API may read it.

``body`` and ``options`` are flat lists of strings that are read as a unit and
never queried individually, so they are stored as JSON rather than as child
tables — a deliberate tradeoff against over-normalizing.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, generate_uuid


class Lesson(Base, TimestampMixin):
    """A lesson — the top-level content entity, addressed by stable slug.

    ``slug`` is the stable public identifier and the key that
    ``lesson_progress`` references, so it must never change silently.
    """

    __tablename__ = "lessons"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=generate_uuid,
    )
    slug: Mapped[str] = mapped_column(
        String(100),
        unique=True,
        nullable=False,
        index=True,
        comment="Stable public identifier; referenced by lesson_progress",
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    topic: Mapped[str] = mapped_column(String(100), nullable=False)
    difficulty: Mapped[str] = mapped_column(String(20), nullable=False)
    estimated_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    ordering: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="Catalog position, 1-based",
    )
    published: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=text("false"),
        comment="Server-authoritative publication state",
    )
    published_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="When the lesson was last published",
    )

    sections: Mapped[list["LessonSection"]] = relationship(
        back_populates="lesson",
        cascade="all, delete-orphan",
        order_by="LessonSection.ordering",
    )

    __table_args__ = (
        Index("ix_lessons_ordering", "ordering"),
        Index("ix_lessons_published", "published"),
    )

    def __repr__(self) -> str:
        """Return a representation that does not leak content details."""
        return f"<Lesson slug={self.slug!r} published={self.published}>"


class LessonSection(Base):
    """One ordered section of a lesson."""

    __tablename__ = "lesson_sections"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=generate_uuid,
    )
    lesson_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("lessons.id", ondelete="CASCADE"),
        nullable=False,
    )
    section_id: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="Stable section identifier within the lesson (e.g. 'intro')",
    )
    kind: Mapped[str] = mapped_column(String(30), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    body: Mapped[list[str]] = mapped_column(
        JSON,
        nullable=False,
        default=list,
        comment="Ordered prose paragraphs",
    )
    element_symbol: Mapped[str | None] = mapped_column(
        String(10),
        nullable=True,
        comment="Chemistry reference: element for a live spotlight",
    )
    molecule_input: Mapped[str | None] = mapped_column(
        String(200),
        nullable=True,
        comment="Chemistry reference: formula/SMILES/InChI for a live spotlight",
    )
    ordering: Mapped[int] = mapped_column(Integer, nullable=False)

    lesson: Mapped[Lesson] = relationship(back_populates="sections")
    questions: Mapped[list["LessonQuestion"]] = relationship(
        back_populates="section",
        cascade="all, delete-orphan",
        order_by="LessonQuestion.ordering",
    )

    __table_args__ = (
        UniqueConstraint("lesson_id", "section_id", name="uq_section_lesson_id"),
        Index("ix_lesson_sections_lesson", "lesson_id", "ordering"),
    )


class LessonQuestion(Base):
    """One practice question, including the server-only answer key."""

    __tablename__ = "lesson_questions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=generate_uuid,
    )
    lesson_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("lessons.id", ondelete="CASCADE"),
        nullable=False,
    )
    section_id: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="Owning section, unique with lesson_id",
    )
    question_id: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="Stable question identifier within the lesson",
    )
    kind: Mapped[str] = mapped_column(String(20), nullable=False)
    prompt: Mapped[str] = mapped_column(Text, nullable=False)
    correct: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Answer key — server-only, never sent to students",
    )
    explanation: Mapped[str] = mapped_column(Text, nullable=False)
    options: Mapped[list[str]] = mapped_column(
        JSON,
        nullable=False,
        default=list,
        comment="Choice labels for multiple-choice questions",
    )
    ordering: Mapped[int] = mapped_column(Integer, nullable=False)

    section: Mapped[LessonSection] = relationship(back_populates="questions")

    __table_args__ = (
        UniqueConstraint("lesson_id", "question_id", name="uq_question_lesson_id"),
        # Enforce that a question really belongs to a section of its lesson.
        ForeignKeyConstraint(
            ["lesson_id", "section_id"],
            ["lesson_sections.lesson_id", "lesson_sections.section_id"],
            ondelete="CASCADE",
        ),
        Index("ix_lesson_questions_lesson", "lesson_id", "ordering"),
    )