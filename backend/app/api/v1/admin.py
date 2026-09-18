"""Admin content-management API (M26).

All endpoints require authentication AND the admin flag
(``get_current_admin``). Unlike the student learning API, these responses
include answer keys and drafts, so the schemas here are deliberately separate
from the student DTOs in ``app.api.v1.learning``.

Endpoints:
    GET  /api/v1/admin/lessons             → all lessons, drafts included
    GET  /api/v1/admin/lessons/{slug}      → one lesson, answer keys included
    POST /api/v1/admin/lessons             → create (saved as draft)
    PUT  /api/v1/admin/lessons/{slug}      → replace content (state preserved)
    POST /api/v1/admin/lessons/{slug}/publish    → publish (validates first)
    POST /api/v1/admin/lessons/{slug}/unpublish  → back to draft

Publishing is refused while validation fails, so the student API can never be
handed content it cannot render or grade.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_admin
from app.db.session import get_db_session
from app.learning.content import Lesson, Question, Section
from app.models.content import Lesson as LessonRow
from app.models.user import User
from app.services.content_admin import AdminContentService, ContentValidationError
from app.services.learning import LearningError

router = APIRouter(prefix="/admin", tags=["admin-content"])


# --- Admin DTOs (answer keys included — never reuse student schemas) ---


class AdminQuestion(BaseModel):
    """A question as seen by an author, including the answer key."""

    id: str
    kind: str
    prompt: str
    correct: str
    explanation: str
    options: list[str]
    ordering: int


class AdminSection(BaseModel):
    """A section as seen by an author."""

    id: str
    kind: str
    title: str
    body: list[str]
    element_symbol: str | None
    molecule_input: str | None
    ordering: int
    questions: list[AdminQuestion]


class AdminLesson(BaseModel):
    """A lesson as seen by an author, including drafts and answer keys."""

    slug: str
    title: str
    description: str
    topic: str
    difficulty: str
    estimated_minutes: int
    ordering: int
    published: bool
    published_at: str | None
    created_at: str | None
    updated_at: str | None
    sections: list[AdminSection]


class AdminLessonSummary(BaseModel):
    """Catalog entry for the admin lesson list."""

    slug: str
    title: str
    topic: str
    difficulty: str
    estimated_minutes: int
    ordering: int
    published: bool
    section_count: int
    question_count: int
    updated_at: str | None


class AdminLessonList(BaseModel):
    """The admin lesson list."""

    lessons: list[AdminLessonSummary]


class AdminErrorDetail(BaseModel):
    """Stable machine-readable error code plus a user-facing message."""

    code: str
    message: str


class AdminValidationErrorDetail(AdminErrorDetail):
    """Validation failure with field-level errors."""

    errors: list[dict[str, str]]


# --- Request DTOs ---


class AdminQuestionUpsert(BaseModel):
    """Incoming question payload."""

    id: str = Field(min_length=1, max_length=50)
    kind: str = Field(min_length=1, max_length=20)
    prompt: str = Field(min_length=1, max_length=2000)
    correct: str = Field(min_length=1, max_length=500)
    explanation: str = Field(min_length=1, max_length=2000)
    options: list[str] = Field(default_factory=list, max_length=10)


class AdminSectionUpsert(BaseModel):
    """Incoming section payload."""

    id: str = Field(min_length=1, max_length=50)
    kind: str = Field(min_length=1, max_length=30)
    title: str = Field(min_length=1, max_length=200)
    body: list[str] = Field(default_factory=list, max_length=20)
    element_symbol: str | None = Field(default=None, max_length=10)
    molecule_input: str | None = Field(default=None, max_length=200)
    questions: list[AdminQuestionUpsert] = Field(default_factory=list, max_length=30)


class AdminLessonUpsert(BaseModel):
    """Incoming lesson payload (create and update)."""

    slug: str = Field(min_length=1, max_length=100)
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(min_length=1, max_length=2000)
    subject: str = Field(min_length=1, max_length=100)
    difficulty: str = Field(min_length=1, max_length=20)
    estimated_minutes: int = Field(ge=1)
    order: int = Field(ge=1)
    sections: list[AdminSectionUpsert]


# --- Helpers ---


async def get_admin_service(
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> AdminContentService:
    """Provide an AdminContentService bound to the request's DB session."""
    return AdminContentService(db)


def _to_domain(payload: AdminLessonUpsert) -> Lesson:
    """Map an admin payload onto the content-domain dataclasses."""
    sections = tuple(
        Section(
            id=section.id,
            kind=section.kind,
            title=section.title,
            body=tuple(section.body),
            element_symbol=section.element_symbol,
            molecule_input=section.molecule_input,
            question_ids=tuple(question.id for question in section.questions),
        )
        for section in payload.sections
    )
    questions = tuple(
        Question(
            id=question.id,
            kind=question.kind,
            prompt=question.prompt,
            correct=question.correct,
            explanation=question.explanation,
            options=tuple(question.options),
        )
        for section in payload.sections
        for question in section.questions
    )
    return Lesson(
        id=payload.slug,
        slug=payload.slug,
        title=payload.title,
        description=payload.description,
        subject=payload.subject,
        difficulty=payload.difficulty,
        estimated_minutes=payload.estimated_minutes,
        order=payload.order,
        sections=sections,
        questions=questions,
    )


def _iso(value: object) -> str | None:
    """Format a datetime as ISO-8601, or None when absent."""
    return value.isoformat() if hasattr(value, "isoformat") else None


def _lesson_response(row: LessonRow) -> AdminLesson:
    """Build the admin lesson DTO, including answer keys."""
    sections = sorted(row.sections or [], key=lambda s: s.ordering)
    return AdminLesson(
        slug=row.slug,
        title=row.title,
        description=row.description,
        topic=row.topic,
        difficulty=row.difficulty,
        estimated_minutes=row.estimated_minutes,
        ordering=row.ordering,
        published=row.published,
        published_at=_iso(row.published_at),
        created_at=_iso(row.created_at),
        updated_at=_iso(row.updated_at),
        sections=[
            AdminSection(
                id=section.section_id,
                kind=section.kind,
                title=section.title,
                body=list(section.body or []),
                element_symbol=section.element_symbol,
                molecule_input=section.molecule_input,
                ordering=section.ordering,
                questions=[
                    AdminQuestion(
                        id=question.question_id,
                        kind=question.kind,
                        prompt=question.prompt,
                        correct=question.correct,
                        explanation=question.explanation,
                        options=list(question.options or []),
                        ordering=question.ordering,
                    )
                    for question in sorted(
                        section.questions or [], key=lambda q: q.ordering
                    )
                ],
            )
            for section in sections
        ],
    )


def _summary(row: LessonRow) -> AdminLessonSummary:
    """Build one admin catalog entry."""
    return AdminLessonSummary(
        slug=row.slug,
        title=row.title,
        topic=row.topic,
        difficulty=row.difficulty,
        estimated_minutes=row.estimated_minutes,
        ordering=row.ordering,
        published=row.published,
        section_count=len(row.sections or []),
        question_count=sum(len(s.questions or []) for s in row.sections or []),
        updated_at=_iso(row.updated_at),
    )


# --- Endpoints ---


def _http_error(exc: LearningError, status_code: int) -> HTTPException:
    """Map a service error onto a structured HTTP error."""
    return HTTPException(
        status_code=status_code,
        detail={"code": exc.code, "message": exc.message},
    )


@router.get(
    "/lessons",
    response_model=AdminLessonList,
    summary="List all lessons (drafts included)",
)
async def admin_list_lessons(
    service: Annotated[AdminContentService, Depends(get_admin_service)],
    _admin: Annotated[User, Depends(get_current_admin)],
) -> AdminLessonList:
    """Return every lesson, including unpublished drafts."""
    return AdminLessonList(lessons=[_summary(row) for row in await service.list_lesson_rows()])


@router.get(
    "/lessons/{slug}",
    response_model=AdminLesson,
    summary="Retrieve a lesson (answer keys included)",
    responses={404: {"model": AdminErrorDetail}},
)
async def admin_get_lesson(
    slug: str,
    service: Annotated[AdminContentService, Depends(get_admin_service)],
    _admin: Annotated[User, Depends(get_current_admin)],
) -> AdminLesson:
    """Return one lesson including drafts and answer keys."""
    try:
        row = await service.get_lesson_row(slug)
    except LearningError as exc:
        raise _http_error(exc, 404) from exc
    return _lesson_response(row)


@router.post(
    "/lessons",
    response_model=AdminLesson,
    status_code=201,
    summary="Create a lesson (saved as a draft)",
    responses={
        404: {"model": AdminErrorDetail},
        409: {"model": AdminErrorDetail, "description": "Duplicate slug"},
        422: {"model": AdminValidationErrorDetail, "description": "Invalid content"},
    },
)
async def admin_create_lesson(
    payload: AdminLessonUpsert,
    service: Annotated[AdminContentService, Depends(get_admin_service)],
    _admin: Annotated[User, Depends(get_current_admin)],
) -> AdminLesson:
    """Create a lesson. New lessons are always drafts until published."""
    try:
        await service.create_lesson(_to_domain(payload))
    except ContentValidationError as exc:
        raise HTTPException(
            status_code=422,
            detail={
                "code": "validation_failed",
                "message": exc.first_message,
                "errors": exc.errors,
            },
        ) from exc
    except LearningError as exc:
        raise _http_error(exc, 409 if exc.code == "duplicate_slug" else 404) from exc
    row = await service.get_lesson_row(payload.slug)
    return _lesson_response(row)


@router.put(
    "/lessons/{slug}",
    response_model=AdminLesson,
    summary="Replace a lesson's content",
    responses={
        400: {"model": AdminErrorDetail, "description": "Slug mismatch"},
        404: {"model": AdminErrorDetail},
        422: {"model": AdminValidationErrorDetail, "description": "Invalid content"},
    },
)
async def admin_update_lesson(
    slug: str,
    payload: AdminLessonUpsert,
    service: Annotated[AdminContentService, Depends(get_admin_service)],
    _admin: Annotated[User, Depends(get_current_admin)],
) -> AdminLesson:
    """Replace a lesson's sections and questions, keeping its publish state."""
    try:
        await service.update_lesson(slug, _to_domain(payload))
    except ContentValidationError as exc:
        raise HTTPException(
            status_code=422,
            detail={
                "code": "validation_failed",
                "message": exc.first_message,
                "errors": exc.errors,
            },
        ) from exc
    except LearningError as exc:
        status_code = 400 if exc.code == "slug_mismatch" else 404
        raise _http_error(exc, status_code) from exc
    row = await service.get_lesson_row(slug)
    return _lesson_response(row)


@router.post(
    "/lessons/{slug}/publish",
    response_model=AdminLesson,
    summary="Publish a lesson",
    responses={
        404: {"model": AdminErrorDetail},
        422: {"model": AdminValidationErrorDetail, "description": "Invalid content"},
    },
)
async def admin_publish_lesson(
    slug: str,
    service: Annotated[AdminContentService, Depends(get_admin_service)],
    _admin: Annotated[User, Depends(get_current_admin)],
) -> AdminLesson:
    """Publish a lesson. Invalid content is refused, not published."""
    try:
        await service.publish(slug)
    except ContentValidationError as exc:
        raise HTTPException(
            status_code=422,
            detail={
                "code": "validation_failed",
                "message": exc.first_message,
                "errors": exc.errors,
            },
        ) from exc
    except LearningError as exc:
        raise _http_error(exc, 404) from exc
    return _lesson_response(await service.get_lesson_row(slug))


# --- Preview DTOs (student view, admin-only) ---


class PreviewQuestionPublic(BaseModel):
    """A question as students see it (no answer key)."""

    id: str
    kind: str
    prompt: str
    options: list[str]


class PreviewSectionPublic(BaseModel):
    """A section as students see it."""

    id: str
    kind: str
    title: str
    body: list[str]
    element_symbol: str | None
    molecule_input: str | None
    questions: list[PreviewQuestionPublic]


class PreviewLessonResponse(BaseModel):
    """A lesson as students would see it — admin preview endpoint."""

    id: str
    slug: str
    title: str
    description: str
    subject: str
    difficulty: str
    estimated_minutes: int
    sections: list[PreviewSectionPublic]


@router.get(
    "/lessons/{slug}/preview",
    response_model=PreviewLessonResponse,
    summary="Preview a lesson as a student would see it",
    responses={404: {"model": AdminErrorDetail}},
)
async def admin_preview_lesson(
    slug: str,
    service: Annotated[AdminContentService, Depends(get_admin_service)],
    _admin: Annotated[User, Depends(get_current_admin)],
) -> PreviewLessonResponse:
    """Return a lesson in student-safe format for admin preview.

    Answer keys are stripped.  The lesson need not be published.
    """
    try:
        lesson = await service.get_lesson(slug)
    except LearningError as exc:
        raise _http_error(exc, 404) from exc
    sections_out: list[PreviewSectionPublic] = []
    for section in lesson.sections:
        questions_out = [
            PreviewQuestionPublic(
                id=q.id, kind=q.kind, prompt=q.prompt, options=list(q.options)
            )
            for q in (lesson.question_by_id(qid) for qid in section.question_ids)
            if q is not None
        ]
        sections_out.append(
            PreviewSectionPublic(
                id=section.id,
                kind=section.kind,
                title=section.title,
                body=list(section.body),
                element_symbol=section.element_symbol,
                molecule_input=section.molecule_input,
                questions=questions_out,
            )
        )
    return PreviewLessonResponse(
        id=lesson.id,
        slug=lesson.slug,
        title=lesson.title,
        description=lesson.description,
        subject=lesson.subject,
        difficulty=lesson.difficulty,
        estimated_minutes=lesson.estimated_minutes,
        sections=sections_out,
    )


@router.post(
    "/lessons/{slug}/unpublish",
    response_model=AdminLesson,
    summary="Return a lesson to draft",
    responses={404: {"model": AdminErrorDetail}},
)
async def admin_unpublish_lesson(
    slug: str,
    service: Annotated[AdminContentService, Depends(get_admin_service)],
    _admin: Annotated[User, Depends(get_current_admin)],
) -> AdminLesson:
    """Unpublish a lesson so students can no longer see it."""
    try:
        await service.unpublish(slug)
    except LearningError as exc:
        raise _http_error(exc, 404) from exc
    return _lesson_response(await service.get_lesson_row(slug))
