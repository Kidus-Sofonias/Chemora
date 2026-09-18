"""Content repository — persistence for educational content (M26).

The repository owns every SQLAlchemy query for content so that neither route
handlers nor services touch the database directly:

    Route → Service → ContentRepository → SQLAlchemy → PostgreSQL

Reads return the same domain dataclasses the M24/M25 seed layer produced, so
the student learning API contract and the deterministic grading logic are
unchanged: only *where* the content comes from has changed.

Load strategy: lessons are fetched with eager (``selectinload``) section and
question loading — three queries for a full lesson tree and no N+1 loops.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.learning.content import Lesson, Question, Section
from app.models.content import LessonQuestion, LessonSection
from app.models.content import Lesson as LessonRow

# Eager-load the full lesson tree in a fixed number of queries.
_LESSON_LOAD = selectinload(LessonRow.sections).selectinload(LessonSection.questions)


class ContentRepository:
    """Data-access layer for educational content."""

    def __init__(self, db: AsyncSession) -> None:
        """Initialize with an async database session."""
        self._db = db

    # ── Reads ─────────────────────────────────────────────────────────

    async def list_lessons(self, *, include_unpublished: bool = False) -> list[Lesson]:
        """Return lessons in catalog order as domain dataclasses.

        Args:
            include_unpublished: When True (admin only) drafts are included.
        """
        stmt = select(LessonRow).options(_LESSON_LOAD).order_by(
            LessonRow.ordering, LessonRow.slug
        )
        if not include_unpublished:
            stmt = stmt.where(LessonRow.published.is_(True))
        result = await self._db.execute(stmt)
        return [self._to_domain(row) for row in result.scalars().all()]

    async def get_lesson(
        self, slug: str, *, include_unpublished: bool = False
    ) -> Lesson | None:
        """Return one lesson by slug, or None when absent (or unpublished)."""
        row = await self._get_row(slug, include_unpublished=include_unpublished)
        return None if row is None else self._to_domain(row)

    async def get_lesson_row(self, slug: str) -> LessonRow | None:
        """Return the raw lesson row (admin operations, drafts included)."""
        return await self._get_row(slug, include_unpublished=True)

    async def slug_exists(self, slug: str) -> bool:
        """Return True when a lesson with this slug already exists."""
        result = await self._db.execute(
            select(LessonRow.id).where(LessonRow.slug == slug).limit(1)
        )
        return result.scalar_one_or_none() is not None

    async def list_lesson_rows(
        self, *, include_unpublished: bool = False
    ) -> list[LessonRow]:
        """Return raw lesson rows in catalog order (admin catalog).

        Rows carry the publication state the admin UI needs, which the domain
        dataclasses deliberately do not.
        """
        stmt = select(LessonRow).options(_LESSON_LOAD).order_by(
            LessonRow.ordering, LessonRow.slug
        )
        if not include_unpublished:
            stmt = stmt.where(LessonRow.published.is_(True))
        result = await self._db.execute(stmt)
        return list(result.scalars().all())

    # ── Writes ────────────────────────────────────────────────────────

    async def upsert_lesson(self, lesson: Lesson, *, published: bool) -> None:
        """Insert or replace a lesson and all of its children.

        Deterministic and idempotent: an existing lesson with the same slug is
        updated in place and its sections/questions are replaced wholesale, so
        re-running the seed command never duplicates content.

        Section and question ordering is derived from their position in the
        incoming lesson, which keeps ordering coherent by construction.
        """
        row = await self.get_lesson_row(lesson.slug)
        if row is None:
            row = LessonRow(slug=lesson.slug)
            self._db.add(row)

        row.title = lesson.title
        row.description = lesson.description
        row.topic = lesson.subject
        row.difficulty = lesson.difficulty
        row.estimated_minutes = lesson.estimated_minutes
        row.ordering = lesson.order
        row.published = published
        # Explicitly delete old children first to avoid UNIQUE constraint
        # violations during the same flush — SQLAlchemy's cascade may insert
        # new rows before removing old ones when reusing the same identity.
        if row.sections:
            for existing in list(row.sections):
                await self._db.delete(existing)
            row.sections = []
            await self._db.flush()
        # Now build and attach the new children.
        row.sections = [
            self._build_section_row(
                section,
                [q for q in lesson.questions if q.id in section.question_ids],
                position,
            )
            for position, section in enumerate(lesson.sections, start=1)
        ]
        await self._db.flush()

    async def set_published(self, slug: str, published: bool) -> None:
        """Set the publication state of a lesson.

        Raises:
            KeyError: When the lesson does not exist.
        """
        row = await self.get_lesson_row(slug)
        if row is None:
            raise KeyError(slug)
        row.published = published
        row.published_at = datetime.now(timezone.utc) if published else None
        await self._db.flush()

    # ── Internals ─────────────────────────────────────────────────────

    async def _get_row(self, slug: str, *, include_unpublished: bool) -> LessonRow | None:
        """Fetch one lesson row, optionally restricted to published ones."""
        stmt = select(LessonRow).where(LessonRow.slug == slug).options(_LESSON_LOAD)
        if not include_unpublished:
            stmt = stmt.where(LessonRow.published.is_(True))
        result = await self._db.execute(stmt)
        return result.scalar_one_or_none()

    def _build_section_row(
        self, section: Section, questions: list[Question], ordering: int
    ) -> LessonSection:
        """Build a section row with its questions from a domain section.

        ``lesson_id`` is populated by the ORM from the parent lesson.
        """
        return LessonSection(
            section_id=section.id,
            kind=section.kind,
            title=section.title,
            body=list(section.body),
            element_symbol=section.element_symbol,
            molecule_input=section.molecule_input,
            ordering=ordering,
            questions=[
                LessonQuestion(
                    section_id=section.id,
                    question_id=question.id,
                    kind=question.kind,
                    prompt=question.prompt,
                    correct=question.correct,
                    explanation=question.explanation,
                    options=list(question.options),
                    ordering=position,
                )
                for position, question in enumerate(questions, start=1)
            ],
        )

    def _to_domain(self, row: LessonRow) -> Lesson:
        """Map a lesson row (with eager children) to the domain dataclass."""
        sections = sorted(row.sections or [], key=lambda s: s.ordering)
        return Lesson(
            id=row.slug,
            slug=row.slug,
            title=row.title,
            description=row.description,
            subject=row.topic,
            difficulty=row.difficulty,
            estimated_minutes=row.estimated_minutes,
            order=row.ordering,
            sections=tuple(
                Section(
                    id=section.section_id,
                    kind=section.kind,
                    title=section.title,
                    body=tuple(section.body or []),
                    element_symbol=section.element_symbol,
                    molecule_input=section.molecule_input,
                    question_ids=tuple(
                        q.question_id
                        for q in sorted(section.questions or [], key=lambda x: x.ordering)
                    ),
                )
                for section in sections
            ),
            questions=tuple(
                Question(
                    id=question.question_id,
                    kind=question.kind,
                    prompt=question.prompt,
                    correct=question.correct,
                    explanation=question.explanation,
                    options=tuple(question.options or []),
                )
                for question in sorted(
                    (q for s in sections for q in s.questions or []),
                    key=lambda q: q.ordering,
                )
            ),
        )