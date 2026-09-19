"""Student-safe content retrieval for the AI tutor (M29).

Security boundary:
- Only **published** lessons are ever retrieved, through the same
  ``ContentRepository`` rules the student learning API uses (drafts resolve
  to nothing, so a draft is not even discoverable by enumeration).
- The serialized context contains section prose and question **prompts**
  only. Correct answers and admin metadata are never included — the tutor
  cannot leak what it was never given.

Retrieval strategy (M29): deterministic keyword-overlap scoring between the
student's question and each published lesson's text. Bounded, predictable,
testable, and intentionally simple — a vector database is not required for
the first implementation and the interface is replaceable later.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from sqlalchemy.ext.asyncio import AsyncSession

from app.learning.content import Lesson
from app.repositories.content import ContentRepository

logger = logging.getLogger(__name__)

#: Maximum lessons included in one tutoring context.
_MAX_LESSONS = 2
#: Maximum characters of lesson text included per lesson.
_MAX_CHARS_PER_LESSON = 1800
#: Words below this length are ignored as search terms.
_MIN_WORD_LENGTH = 3

_SYSTEM_PROMPT = (
    "You are the Chemora chemistry tutor for a student. Teach clearly and "
    "encouragingly: guide understanding rather than just handing over answers. "
    "You have chemistry tools available: when a question needs a deterministic "
    "chemistry value (a molar mass, a molecular formula, an electron "
    "configuration, a descriptor), call the matching tool and use its result "
    "verbatim — never compute or guess those values yourself. If relevant "
    "lesson content is provided, teach from it; do not contradict it. If you "
    "are unsure of something, say so plainly. Keep answers concise and "
    "student-appropriate, and stay within chemistry learning topics."
)


@dataclass(slots=True)
class RetrievedContext:
    """Student-safe tutoring context built from published lessons."""

    system_prompt: str = _SYSTEM_PROMPT
    lesson_slugs: list[str] = field(default_factory=list)
    context_text: str = ""


class ContentRetriever:
    """Deterministic, student-safe retrieval over published lessons."""

    def __init__(self, db: AsyncSession) -> None:
        """Initialize with the request's database session."""
        self._db = db

    async def retrieve(self, question: str, lesson_slug: str | None) -> RetrievedContext:
        """Build the tutoring context for a question.

        Args:
            question: The student's (already length-limited) question.
            lesson_slug: Optional current-lesson context suggested by the
                client. Verified server-side — the lesson must be published,
                otherwise it is ignored.

        Returns:
            Student-safe text from at most ``_MAX_LESSONS`` published
            lessons (never answer keys, never drafts).
        """
        lessons = await ContentRepository(self._db).list_lessons()
        if not lessons:
            return RetrievedContext()

        selected = self._select(lessons, question, lesson_slug)
        parts: list[str] = []
        slugs: list[str] = []
        for lesson in selected:
            text = self._lesson_text(lesson)
            if text:
                parts.append(text)
                slugs.append(lesson.slug)
        return RetrievedContext(lesson_slugs=slugs, context_text="\n\n".join(parts))

    # ── Internals ─────────────────────────────────────────────────────

    def _select(
        self, lessons: list[Lesson], question: str, lesson_slug: str | None
    ) -> list[Lesson]:
        """Pick the lessons for this question (deterministic scoring)."""
        by_slug = {lesson.slug: lesson for lesson in lessons}
        selected: list[Lesson] = []

        # 1. The suggested current lesson wins its slot — only if published
        #    (it comes from the published list, so presence is the check).
        if lesson_slug and lesson_slug in by_slug:
            selected.append(by_slug[lesson_slug])

        # 2. Keyword-overlap ranking over the remaining published lessons.
        remaining = [lesson for lesson in lessons if lesson not in selected]
        if len(selected) < _MAX_LESSONS:
            scored = sorted(
                ((self._score(lesson, question), lesson) for lesson in remaining),
                key=lambda pair: (-pair[0], pair[1].slug),
            )
            for score, lesson in scored:
                if len(selected) >= _MAX_LESSONS:
                    break
                if score > 0:
                    selected.append(lesson)
        return selected

    @staticmethod
    def _score(lesson: Lesson, question: str) -> int:
        """Keyword overlap between the question and the lesson's text."""
        question_terms = _terms(question)
        if not question_terms:
            return 0
        lesson_terms = _terms(
            " ".join(
                [lesson.title, lesson.description, lesson.subject]
                + [body for section in lesson.sections for body in section.body]
            )
        )
        return len(question_terms & lesson_terms)

    @staticmethod
    def _lesson_text(lesson: Lesson) -> str:
        """Serialize a lesson to student-safe prompt text (no answer keys)."""
        lines = [f"Lesson: {lesson.title} ({lesson.slug})", lesson.description, ""]
        for section in lesson.sections:
            lines.append(f"## {section.title}")
            lines.extend(section.body)
            # Question prompts are student-visible; answers are never included.
            for question_id in section.question_ids:
                question = lesson.question_by_id(question_id)
                if question is not None:
                    lines.append(f"Practice question: {question.prompt}")
        return "\n".join(lines)[:_MAX_CHARS_PER_LESSON]


def _terms(text: str) -> set[str]:
    """Lowercased significant words of a text."""
    return {
        word
        for word in "".join(c if c.isalnum() else " " for c in text.lower()).split()
        if len(word) >= _MIN_WORD_LENGTH
    }

