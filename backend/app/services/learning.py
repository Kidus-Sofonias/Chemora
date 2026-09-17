"""Learning service — lessons, answer validation, and progress.

Architecture:
- Lesson content comes from the isolated seed layer (``app.learning.content``)
  and can later move to a database/CMS without changing this contract.
- Chemistry values shown in lessons are NOT computed here;
  ``chemistry_spotlight`` sections reference elements by symbol and the client
  renders live data from the existing element API
  (``GET /api/v1/elements/{symbol}``, backed by ChemEngine).
- Question answers are validated server-side and deterministically (exact /
  numeric comparison). Correct answers never leave the server.
- Progress is persisted per authenticated user in the ``lesson_progress`` table.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.learning.content import Lesson, get_lesson_by_slug, get_lessons
from app.models.learning import LessonProgress


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


class LearningService:
    """Application-layer facade over the content layer and progress store."""

    def __init__(self, db: AsyncSession) -> None:
        """Initialize with an async database session for progress."""
        self._db = db

    # ── Lessons ───────────────────────────────────────────────────────

    @staticmethod
    def list_lessons() -> list[Lesson]:
        """Return all lessons in curated order."""
        return list(get_lessons())

    @staticmethod
    def get_lesson(slug: str) -> Lesson:
        """Return a lesson by slug.

        Raises:
            LearningError: If the slug is unknown (``lesson_not_found``).
        """
        lesson = get_lesson_by_slug(slug)
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
        is_correct = _normalize_answer(answer) == _normalize_answer(question.correct)
        return is_correct, question.explanation

    # ── Progress ──────────────────────────────────────────────────────

    async def get_progress(self, user_id: uuid.UUID, slug: str) -> LessonProgress:
        """Return the user's progress row for a lesson, creating an empty one.

        Raises:
            LearningError: If the lesson slug is unknown.
        """
        lesson = self.get_lesson(slug)
        progress = await self._find_progress(user_id, slug)
        if progress is None:
            progress = LessonProgress(
                user_id=user_id,
                lesson_slug=slug,
                completed_sections=[],
                answers={},
            )
            self._db.add(progress)
            await self._db.flush()
        # Re-derive completion in case content changed since the last visit.
        self._sync_completion(progress, lesson)
        return progress

    async def complete_section(
        self, user_id: uuid.UUID, slug: str, section_id: str
    ) -> LessonProgress:
        """Mark one section complete and return updated progress.

        Lesson completion is set automatically when every section is done.

        Raises:
            LearningError: If the lesson or section id is unknown.
        """
        lesson = self.get_lesson(slug)
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
        lesson = self.get_lesson(slug)
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


