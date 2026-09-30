"""Learning service — lessons, answer validation, and progress.

Architecture:
- Lesson content is read from PostgreSQL through the content repository
  (M26); the student-facing contract is unchanged. The seeded definitions in
  ``app.learning.content`` are now the *seed source* that populates the
  database (``app.learning.seed``).
- Chemistry values shown in lessons are NOT computed here;
  ``chemistry_spotlight`` sections reference elements by symbol and the client
  renders live data from the existing element API
  (``GET /api/v1/elements/{symbol}``, backed by ChemEngine).
- Question answers are validated server-side and deterministically. Text and
  numeric kinds use normalized comparison; ``formula`` and ``element`` kinds
  are canonicalized by ChemEngine. Correct answers never leave the server.
- Progress is persisted per authenticated user in the ``lesson_progress`` table.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.learning.content import Lesson, Question
from app.models.learning import LessonProgress
from app.repositories.content import ContentRepository
from app.services.chemistry_validate import (
    canonicalize_formula as _canonicalize_formula,
)
from app.services.chemistry_validate import resolve_element as _resolve_element


class LearningError(Exception):
    """A stable, client-safe learning error."""

    def __init__(self, code: str, message: str) -> None:
        """Initialize with a stable code and a user-facing message."""
        super().__init__(message)
        self.code = code
        self.message = message


def _normalize_answer(answer: str) -> str:
    """Normalize a submitted answer for deterministic comparison."""
    return " ".join(answer.strip().lower().split())


# Earliest comparable epoch for progress rows that were never persisted with a
# real ``updated_at`` (e.g. transient rows built in unit tests).
_RECOMMEND_EPOCH = datetime(2000, 1, 1, tzinfo=timezone.utc)


def recommend_next_lesson(
    lessons: list[Lesson],
    progress_by_slug: dict[str, LessonProgress],
) -> tuple[str | None, str]:
    """Deterministically recommend the next lesson from catalog order + progress.

    The rule uses ONLY existing, server-authoritative inputs — catalog ordering
    and persisted progress. No new models, no engagement scoring, no recency
    bias in the *selection* (recency only breaks exact ties):

      1. Resume — if the student has started but not finished any lesson,
         recommend the in-progress lesson with the greatest completion. Ties
         break on most-recent activity (``updated_at``) then earliest catalog
         ``order``.
      2. Next — otherwise recommend the first lesson, by catalog order, that
         the student has not started.
      3. Done — if every cataloged lesson is completed, recommend nothing.

    Returns ``(lesson_slug | None, reason)`` where ``reason`` is a user-facing
    description of the rule that applied.
    """

    def _percent(lesson: Lesson, progress: LessonProgress) -> int:
        section_ids = [section.id for section in lesson.sections]
        total = len(section_ids)
        done = sum(1 for sid in section_ids if sid in progress.completed_sections)
        return round(100 * done / total) if total else 0

    lesson_by_slug = {lesson.slug: lesson for lesson in lessons}
    order_by_slug = {lesson.slug: lesson.order for lesson in lessons}

    started = {
        slug: progress
        for slug, progress in progress_by_slug.items()
        if slug in lesson_by_slug
    }
    in_progress = {
        slug: progress
        for slug, progress in started.items()
        if progress.completed_at is None
    }
    if in_progress:
        best_slug, _best_progress = max(
            in_progress.items(),
            key=lambda item: (
                _percent(lesson_by_slug[item[0]], item[1]),
                item[1].updated_at or _RECOMMEND_EPOCH,
                -order_by_slug.get(item[0], 1 << 30),
            ),
        )
        return best_slug, "Continue where you left off."

    for lesson in lessons:  # already in catalog order
        if lesson.slug not in started:
            return lesson.slug, "Start the next lesson in your learning path."
    return None, "You've completed every lesson — revisit one to review."


class LearningService:
    """Application-layer facade over the content layer and progress store."""

    def __init__(self, db: AsyncSession) -> None:
        """Initialize with an async database session for progress."""
        self._db = db

    # ── Lessons ───────────────────────────────────────────────────────

    async def list_lessons(self) -> list[Lesson]:
        """Return all published lessons in catalog order.

        Content comes from the database-backed content repository (M26).
        Drafts are never visible to students.
        """
        return await ContentRepository(self._db).list_lessons()

    async def get_lesson(self, slug: str) -> Lesson:
        """Return a published lesson by slug.

        Unpublished drafts resolve to "not found" so that a draft slug is not
        discoverable by enumeration.

        Raises:
            LearningError: If the slug is unknown or unpublished
                (``lesson_not_found``).
        """
        lesson = await ContentRepository(self._db).get_lesson(slug)
        if lesson is None:
            raise LearningError("lesson_not_found", "That lesson does not exist.")
        return lesson

    @staticmethod
    def check_answer(
        lesson: Lesson, question_id: str, answer: str
    ) -> tuple[bool, str]:
        """Deterministically validate a submitted answer.

        Returns:
            (is_correct, explanation) — the correct answer itself is never
            returned to the client.

        Raises:
            LearningError: If the question is unknown (``question_not_found``)
                or the answer is empty (``invalid_answer``).
        """
        question = lesson.question_by_id(question_id)
        if question is None:
            raise LearningError(
                "question_not_found",
                "That question does not belong to this lesson.",
            )
        if not answer or not answer.strip():
            raise LearningError("invalid_answer", "Please provide an answer.")
        is_correct = LearningService._grade(question, answer)
        return is_correct, question.explanation

    @staticmethod
    def _grade(question: Question, answer: str) -> bool:
        """Grade a submitted answer according to the question kind.

        Chemistry kinds (``formula`` / ``element``) delegate to ChemEngine so
        that equivalent representations are accepted and chemically different
        ones are rejected — never silently accepted.
        """
        if question.kind == "element":
            expected = _resolve_element(question.correct)
            submitted = _resolve_element(answer)
            if submitted is None:
                raise LearningError(
                    "invalid_answer",
                    "That is not a recognised element. Answer with an element "
                    "symbol, a full name, or an atomic number.",
                )
            return expected is not None and submitted == expected
        if question.kind == "formula":
            expected = _canonicalize_formula(question.correct)
            submitted = _canonicalize_formula(answer)
            if submitted is None:
                raise LearningError(
                    "invalid_answer",
                    "That is not a valid chemical formula. Check the element "
                    "symbols and their capitalisation.",
                )
            return expected is not None and submitted == expected
        # multiple_choice / numeric: normalized exact comparison.
        return _normalize_answer(answer) == _normalize_answer(question.correct)

    # ── Progress ──────────────────────────────────────────────────────

    async def get_progress(self, user_id: uuid.UUID, slug: str) -> LessonProgress:
        """Return the user's progress row for a lesson, creating an empty one.

        Uses IntegrityError recovery to handle concurrent first-time requests
        from the same user for the same lesson safely.

        Raises:
            LearningError: If the lesson slug is unknown.
        """
        lesson = await self.get_lesson(slug)
        progress = await self._find_progress(user_id, slug)
        if progress is None:
            progress = LessonProgress(
                user_id=user_id,
                lesson_slug=slug,
                completed_sections=[],
                answers={},
            )
            self._db.add(progress)
            try:
                await self._db.flush()
            except IntegrityError:
                # Another concurrent request inserted first — re-fetch.
                await self._db.rollback()
                progress = await self._find_progress(user_id, slug)
                if progress is None:
                    raise
        # Re-derive completion in case content changed since the last visit.
        self._sync_completion(progress, lesson)
        return progress

    async def list_progress(self, user_id: uuid.UUID) -> list[LessonProgress]:
        """Return the user's progress rows for every lesson.

        Used by the catalog so a returning student can see where they left
        off. Only lessons the user has actually started have rows.
        """
        result = await self._db.execute(
            select(LessonProgress).where(LessonProgress.user_id == user_id)
        )
        return list(result.scalars().all())

    async def complete_section(
        self, user_id: uuid.UUID, slug: str, section_id: str
    ) -> LessonProgress:
        """Mark one section complete and return updated progress.

        Lesson completion is set automatically when every section is done.

        Raises:
            LearningError: If the lesson or section id is unknown.
        """
        lesson = await self.get_lesson(slug)
        if not any(section.id == section_id for section in lesson.sections):
            raise LearningError(
                "section_not_found",
                "That section does not belong to this lesson.",
            )
        progress = await self.get_progress(user_id, slug)
        if section_id not in progress.completed_sections:
            progress.completed_sections = [*progress.completed_sections, section_id]
        self._sync_completion(progress, lesson)
        return progress

    async def record_answer(
        self, user_id: uuid.UUID, slug: str, question_id: str, answer: str
    ) -> tuple[bool, str, LessonProgress]:
        """Validate an answer, record the outcome, and return the result."""
        lesson = await self.get_lesson(slug)
        correct, explanation = self.check_answer(lesson, question_id, answer)
        progress = await self.get_progress(user_id, slug)
        answers = dict(progress.answers)
        answers[question_id] = correct
        progress.answers = answers
        return correct, explanation, progress

    # ── Internals ─────────────────────────────────────────────────────

    async def _find_progress(
        self, user_id: uuid.UUID, slug: str
    ) -> LessonProgress | None:
        """Find an existing progress row for the user and lesson."""
        result = await self._db.execute(
            select(LessonProgress).where(
                LessonProgress.user_id == user_id,
                LessonProgress.lesson_slug == slug,
            )
        )
        return result.scalar_one_or_none()

    @staticmethod
    def _sync_completion(progress: LessonProgress, lesson: Lesson) -> None:
        """Set/clear completed_at based on section completeness."""
        all_done = all(
            section.id in progress.completed_sections for section in lesson.sections
        )
        if all_done and progress.completed_at is None:
            progress.completed_at = datetime.now(timezone.utc)
        elif not all_done:
            progress.completed_at = None


