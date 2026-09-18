"""Learning API endpoints.

    GET  /api/v1/learning/lessons                          → lesson catalog
    GET  /api/v1/learning/lessons/{slug}                   → full lesson
    GET  /api/v1/learning/lessons/{slug}/progress          → user progress
    POST /api/v1/learning/lessons/{slug}/sections/{sid}/complete
    POST /api/v1/learning/lessons/{slug}/answers           → validate answer

All progress/answer endpoints require authentication. Correct answers are
never serialized to clients; validation happens server-side and
deterministically. Lesson content lives in the backend content layer
(``app.learning.content``); chemistry values referenced by lessons are served
live from ChemEngine via the existing element API (``chemistry_spotlight``
sections name an element) and the existing chemistry explore API (sections
name a molecule by formula/SMILES/InChI).
"""

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_db_session
from app.learning.content import Lesson, Question, Section
from app.models.learning import LessonProgress
from app.models.user import User
from app.services.learning import LearningError, LearningService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/learning", tags=["learning"])


# --- Response Models ---


class QuestionPublic(BaseModel):
    """A practice question as seen by the client (no correct answer)."""

    id: str
    kind: str
    prompt: str
    options: list[str]


class SectionPublic(BaseModel):
    """One lesson section."""

    id: str
    kind: str
    title: str
    body: list[str]
    element_symbol: str | None
    molecule_input: str | None
    questions: list[QuestionPublic]


class LessonSummary(BaseModel):
    """Catalog entry for a lesson."""

    id: str
    slug: str
    title: str
    description: str
    subject: str
    difficulty: str
    estimated_minutes: int
    section_count: int
    question_count: int


class LessonListResponse(BaseModel):
    """The lesson catalog."""

    lessons: list[LessonSummary]


class LessonDetailResponse(BaseModel):
    """A full lesson with ordered sections and public questions."""

    id: str
    slug: str
    title: str
    description: str
    subject: str
    difficulty: str
    estimated_minutes: int
    sections: list[SectionPublic]


class LearningProgressResponse(BaseModel):
    """The authenticated user's progress in one lesson."""

    lesson_slug: str
    completed_sections: list[str]
    answers: dict[str, bool]
    progress_percent: int
    completed: bool


class AnswerResultResponse(BaseModel):
    """Server-side answer validation result. Never includes the answer key."""

    question_id: str
    correct: bool
    explanation: str
    progress: LearningProgressResponse


class LearningErrorDetail(BaseModel):
    """Stable machine-readable error code plus a user-facing message."""

    code: str
    message: str


# --- Helpers ---


def get_learning_service(
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> LearningService:
    """Provide a LearningService bound to the request's DB session."""
    return LearningService(db)


def _progress_response(
    progress: LessonProgress, lesson: Lesson
) -> LearningProgressResponse:
    """Build the progress response, deriving percent from section counts."""
    total = len(lesson.sections)
    done = sum(
        1 for section in lesson.sections if section.id in progress.completed_sections
    )
    percent = round(100 * done / total) if total else 0
    return LearningProgressResponse(
        lesson_slug=progress.lesson_slug,
        completed_sections=list(progress.completed_sections),
        answers=dict(progress.answers),
        progress_percent=percent,
        completed=progress.completed_at is not None,
    )


def _question_public(question: Question) -> QuestionPublic:
    """Strip the correct answer and explanation from a question."""
    return QuestionPublic(
        id=question.id,
        kind=question.kind,
        prompt=question.prompt,
        options=list(question.options),
    )


def _section_public(section: Section, lesson: Lesson) -> SectionPublic:
    """Build the client-safe section, attaching its public questions."""
    questions = [
        _question_public(q)
        for q in (lesson.question_by_id(qid) for qid in section.question_ids)
        if q is not None
    ]
    return SectionPublic(
        id=section.id,
        kind=section.kind,
        title=section.title,
        body=list(section.body),
        element_symbol=section.element_symbol,
        molecule_input=section.molecule_input,
        questions=questions,
    )


def _lesson_detail_response(lesson: Lesson) -> LessonDetailResponse:
    """Build the full lesson response without answer keys."""
    return LessonDetailResponse(
        id=lesson.id,
        slug=lesson.slug,
        title=lesson.title,
        description=lesson.description,
        subject=lesson.subject,
        difficulty=lesson.difficulty,
        estimated_minutes=lesson.estimated_minutes,
        sections=[_section_public(section, lesson) for section in lesson.sections],
    )


# --- Endpoints ---


@router.get(
    "/lessons",
    response_model=LessonListResponse,
    summary="List available lessons",
)
async def list_lessons(
    service: Annotated[LearningService, Depends(get_learning_service)],
) -> LessonListResponse:
    """Return the published lesson catalog in curated order."""
    lessons = await service.list_lessons()
    return LessonListResponse(
        lessons=[
            LessonSummary(
                id=lesson.id,
                slug=lesson.slug,
                title=lesson.title,
                description=lesson.description,
                subject=lesson.subject,
                difficulty=lesson.difficulty,
                estimated_minutes=lesson.estimated_minutes,
                section_count=len(lesson.sections),
                question_count=len(lesson.questions),
            )
            for lesson in lessons
        ]
    )


@router.get(
    "/lessons/{slug}",
    response_model=LessonDetailResponse,
    summary="Retrieve a lesson",
    responses={404: {"model": LearningErrorDetail}},
)
async def get_lesson(
    slug: str,
    service: Annotated[LearningService, Depends(get_learning_service)],
) -> LessonDetailResponse:
    """Return one lesson with its sections and questions (no answer keys)."""
    try:
        lesson = await service.get_lesson(slug)
    except LearningError as exc:
        raise HTTPException(
            status_code=404, detail={"code": exc.code, "message": exc.message}
        ) from exc
    return _lesson_detail_response(lesson)


@router.get(
    "/lessons/{slug}/progress",
    response_model=LearningProgressResponse,
    summary="Get the user's progress in a lesson",
    responses={404: {"model": LearningErrorDetail}},
)
async def get_progress(
    slug: str,
    service: Annotated[LearningService, Depends(get_learning_service)],
    user: Annotated[User, Depends(get_current_user)],
) -> LearningProgressResponse:
    """Return (creating if needed) the user's progress for the lesson."""
    try:
        progress = await service.get_progress(user.id, slug)
    except LearningError as exc:
        raise HTTPException(
            status_code=404, detail={"code": exc.code, "message": exc.message}
        ) from exc
    return _progress_response(progress, await service.get_lesson(slug))


@router.post(
    "/lessons/{slug}/sections/{section_id}/complete",
    response_model=LearningProgressResponse,
    summary="Mark a section complete",
    responses={404: {"model": LearningErrorDetail}},
)
async def complete_section(
    slug: str,
    section_id: str,
    service: Annotated[LearningService, Depends(get_learning_service)],
    user: Annotated[User, Depends(get_current_user)],
) -> LearningProgressResponse:
    """Mark one section complete; the lesson auto-completes when all are done."""
    try:
        progress = await service.complete_section(user.id, slug, section_id)
    except LearningError as exc:
        raise HTTPException(
            status_code=404, detail={"code": exc.code, "message": exc.message}
        ) from exc
    return _progress_response(progress, await service.get_lesson(slug))


class AnswerSubmission(BaseModel):
    """A submitted answer for a lesson question."""

    question_id: str = Field(min_length=1)
    answer: str = Field(min_length=1, max_length=300)


@router.post(
    "/lessons/{slug}/answers",
    response_model=AnswerResultResponse,
    summary="Submit and validate a question answer",
    responses={
        404: {"model": LearningErrorDetail, "description": "Unknown lesson or question"},
        422: {"model": LearningErrorDetail, "description": "Invalid answer"},
    },
)
async def submit_answer(
    slug: str,
    submission: AnswerSubmission,
    service: Annotated[LearningService, Depends(get_learning_service)],
    user: Annotated[User, Depends(get_current_user)],
) -> AnswerResultResponse:
    """Validate the answer server-side and record the outcome."""
    try:
        correct, explanation, progress = await service.record_answer(
            user.id, slug, submission.question_id, submission.answer
        )
    except LearningError as exc:
        status_code = 422 if exc.code == "invalid_answer" else 404
        raise HTTPException(
            status_code=status_code,
            detail={"code": exc.code, "message": exc.message},
        ) from exc
    return AnswerResultResponse(
        question_id=submission.question_id,
        correct=correct,
        explanation=explanation,
        progress=_progress_response(progress, await service.get_lesson(slug)),
    )

