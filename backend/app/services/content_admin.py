"""Admin content service — authoring rules and publication (M26).

Owns the business rules for authoring lessons: what a structurally valid
lesson looks like, which question kinds are supported, and which chemistry
references must resolve before a lesson may be published.

A lesson can always be saved as a draft. Publishing is rejected while
validation fails, so the student API can never be handed content it cannot
render or grade. Answer keys may be managed here but are never exposed to
student endpoints.

Authorization is enforced by the route layer (``get_current_admin``); this
service assumes it has already been applied.
"""

from __future__ import annotations

import re

from sqlalchemy.ext.asyncio import AsyncSession

from app.learning.content import QUESTION_KINDS, SECTION_KINDS, Lesson, Question, Section
from app.models.content import Lesson as LessonRow
from app.repositories.content import ContentRepository
from app.services.chemistry_validate import canonicalize_formula, resolve_element
from app.services.learning import LearningError

_SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
_NUMERIC_RE = re.compile(r"^-?\d+(?:\.\d+)?$")
DIFFICULTIES = ("beginner", "intermediate", "advanced")
MAX_SLUG_LENGTH = 100


class ContentValidationError(Exception):
    """Structured validation failure carrying field-level errors."""

    def __init__(self, errors: list[dict[str, str]]) -> None:
        """Initialize with a list of ``{"field", "message"}`` entries."""
        super().__init__("Content validation failed")
        self.errors = errors

    @property
    def first_message(self) -> str:
        """Return the first user-facing message, for the error envelope."""
        return self.errors[0]["message"] if self.errors else "Content is invalid."


class AdminContentService:
    """Authoring and publication rules over the content repository."""

    def __init__(self, db: AsyncSession) -> None:
        """Initialize with an async database session."""
        self._repo = ContentRepository(db)

    async def list_lessons(self) -> list[Lesson]:
        """Return all lessons including drafts."""
        return await self._repo.list_lessons(include_unpublished=True)

    async def list_lesson_rows(self) -> list[LessonRow]:
        """Return raw lesson rows (drafts included) for the admin catalog."""
        return await self._repo.list_lesson_rows(include_unpublished=True)

    async def get_lesson(self, slug: str) -> Lesson:
        """Return one lesson including drafts.

        Raises:
            LearningError: ``lesson_not_found`` when absent.
        """
        lesson = await self._repo.get_lesson(slug, include_unpublished=True)
        if lesson is None:
            raise LearningError("lesson_not_found", "That lesson does not exist.")
        return lesson

    async def get_lesson_row(self, slug: str) -> LessonRow:
        """Return the raw lesson row (drafts included) for admin DTOs.

        Raises:
            LearningError: ``lesson_not_found`` when absent.
        """
        row = await self._repo.get_lesson_row(slug)
        if row is None:
            raise LearningError("lesson_not_found", "That lesson does not exist.")
        return row

    async def slug_exists(self, slug: str) -> bool:
        """Return True when a lesson with this slug exists."""
        return await self._repo.slug_exists(slug)

    async def create_lesson(self, lesson: Lesson) -> Lesson:
        """Create a lesson as an unpublished draft.

        Raises:
            LearningError: ``duplicate_slug`` when the slug is taken.
            ContentValidationError: when the lesson is structurally invalid.
        """
        errors = self.validate(lesson)
        if errors:
            raise ContentValidationError(errors)
        if await self._repo.slug_exists(lesson.slug):
            raise LearningError(
                "duplicate_slug", "A lesson with that slug already exists."
            )
        await self._repo.upsert_lesson(lesson, published=False)
        return lesson

    async def update_lesson(self, slug: str, lesson: Lesson) -> Lesson:
        """Replace a lesson's content, preserving its publication state.

        Raises:
            LearningError: ``slug_mismatch`` / ``lesson_not_found``.
            ContentValidationError: when the lesson is structurally invalid.
        """
        if lesson.slug != slug:
            raise LearningError(
                "slug_mismatch", "A lesson's slug cannot be changed after creation."
            )
        current = await self._repo.get_lesson_row(slug)
        if current is None:
            raise LearningError("lesson_not_found", "That lesson does not exist.")
        errors = self.validate(lesson)
        if errors:
            raise ContentValidationError(errors)
        await self._repo.upsert_lesson(lesson, published=bool(current.published))
        return lesson

    async def publish(self, slug: str) -> Lesson:
        """Publish a lesson, refusing invalid content.

        Raises:
            ContentValidationError: when the lesson cannot be published.
        """
        lesson = await self.get_lesson(slug)
        errors = self.validate(lesson)
        if errors:
            raise ContentValidationError(errors)
        await self._repo.set_published(slug, True)
        return lesson

    async def unpublish(self, slug: str) -> Lesson:
        """Return a published lesson to draft state."""
        lesson = await self.get_lesson(slug)
        await self._repo.set_published(slug, False)
        return lesson

    # ── Validation ────────────────────────────────────────────────────

    def validate(self, lesson: Lesson) -> list[dict[str, str]]:
        """Validate a lesson and return a list of ``{field, message}`` errors.

        An empty list means the lesson is publishable. The checks cover
        structure, question kinds, and the chemistry references that the
        student API would have to resolve.
        """
        errors: list[dict[str, str]] = []
        self._validate_metadata(lesson, errors)
        self._validate_sections(lesson, errors)
        self._validate_questions(lesson, errors)
        self._validate_chemistry(lesson, errors)
        return errors

    def _validate_metadata(self, lesson: Lesson, errors: list[dict[str, str]]) -> None:
        slug = lesson.slug
        if not slug or not _SLUG_RE.match(slug):
            errors.append(
                {
                    "field": "slug",
                    "message": "Slug may only contain lowercase letters, numbers "
                    "and hyphens (e.g. chemical-formulas).",
                }
            )
        elif len(slug) > MAX_SLUG_LENGTH:
            errors.append(
                {"field": "slug", "message": "Slug must be 100 characters or fewer."}
            )
        if not lesson.title.strip():
            errors.append({"field": "title", "message": "A title is required."})
        if not lesson.description.strip():
            errors.append(
                {"field": "description", "message": "A description is required."}
            )
        if not lesson.subject.strip():
            errors.append({"field": "topic", "message": "A topic is required."})
        if lesson.difficulty not in DIFFICULTIES:
            errors.append(
                {
                    "field": "difficulty",
                    "message": "Difficulty must be beginner, intermediate or advanced.",
                }
            )
        if lesson.estimated_minutes < 1:
            errors.append(
                {
                    "field": "estimated_minutes",
                    "message": "Estimated minutes must be at least 1.",
                }
            )
        if lesson.order < 1:
            errors.append({"field": "ordering", "message": "Ordering must be at least 1."})

    def _validate_sections(self, lesson: Lesson, errors: list[dict[str, str]]) -> None:
        if not lesson.sections:
            errors.append(
                {"field": "sections", "message": "A lesson needs at least one section."}
            )
        seen: set[str] = set()
        for section in lesson.sections:
            if section.id in seen:
                errors.append(
                    {
                        "field": "sections",
                        "message": f"Section id '{section.id}' is duplicated.",
                    }
                )
            seen.add(section.id)
            if section.kind not in SECTION_KINDS:
                errors.append(
                    {
                        "field": "sections",
                        "message": f"Section '{section.id}' has an unsupported type "
                        f"'{section.kind}'.",
                    }
                )
            if not section.title.strip():
                errors.append(
                    {"field": "sections", "message": f"Section '{section.id}' needs a title."}
                )
            if section.kind == "practice":
                if not section.question_ids:
                    errors.append(
                        {
                            "field": "sections",
                            "message": f"Practice section '{section.id}' needs a question.",
                        }
                    )
            elif section.kind == "chemistry_spotlight":
                if bool(section.element_symbol) == bool(section.molecule_input):
                    errors.append(
                        {
                            "field": "sections",
                            "message": f"Spotlight section '{section.id}' must reference "
                            "exactly one of an element or a molecule.",
                        }
                    )
            elif not section.body:
                errors.append(
                    {
                        "field": "sections",
                        "message": f"Section '{section.id}' needs some content.",
                    }
                )

    def _validate_questions(self, lesson: Lesson, errors: list[dict[str, str]]) -> None:
        seen: set[str] = set()
        for question in lesson.questions:
            if question.id in seen:
                errors.append(
                    {
                        "field": "questions",
                        "message": f"Question id '{question.id}' is duplicated.",
                    }
                )
            seen.add(question.id)
            if question.kind not in QUESTION_KINDS:
                errors.append(
                    {
                        "field": "questions",
                        "message": f"Question '{question.id}' has an unsupported type "
                        f"'{question.kind}'.",
                    }
                )
                continue
            if not question.prompt.strip():
                errors.append(
                    {"field": "questions", "message": f"Question '{question.id}' needs a prompt."}
                )
            if not question.correct.strip():
                errors.append(
                    {"field": "questions", "message": f"Question '{question.id}' needs an answer."}
                )
            if not question.explanation.strip():
                errors.append(
                    {
                        "field": "questions",
                        "message": f"Question '{question.id}' needs an explanation.",
                    }
                )
            if question.kind == "multiple_choice":
                if len(question.options) < 2:
                    errors.append(
                        {
                            "field": "questions",
                            "message": f"Question '{question.id}' needs at least two options.",
                        }
                    )
                elif question.correct not in question.options:
                    errors.append(
                        {
                            "field": "questions",
                            "message": f"Question '{question.id}' answer must be one of "
                            "its options.",
                        }
                    )
            elif question.kind == "numeric" and not _NUMERIC_RE.match(
                question.correct.strip()
            ):
                errors.append(
                    {
                        "field": "questions",
                        "message": f"Question '{question.id}' answer must be a number.",
                    }
                )

    def _validate_chemistry(self, lesson: Lesson, errors: list[dict[str, str]]) -> None:
        """Chemistry references must resolve through the engine.

        Grading delegates to ChemEngine, so a question whose expected answer the
        engine cannot canonicalize could never be graded correct — reject it at
        authoring time instead of discovering it in production.
        """
        for question in lesson.questions:
            if question.kind == "formula" and canonicalize_formula(question.correct) is None:
                errors.append(
                    {
                        "field": "questions",
                        "message": f"Question '{question.id}' answer is not a valid "
                        "chemical formula.",
                    }
                )
            if question.kind == "element" and resolve_element(question.correct) is None:
                errors.append(
                    {
                        "field": "questions",
                        "message": f"Question '{question.id}' answer does not name a "
                        "recognised element.",
                    }
                )
        for section in lesson.sections:
            symbol = section.element_symbol
            if symbol and resolve_element(symbol) is None:
                errors.append(
                    {
                        "field": "sections",
                        "message": f"Section '{section.id}' references an unknown "
                        f"element '{symbol}'.",
                    }
                )