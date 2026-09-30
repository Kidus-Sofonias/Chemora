"""Learning API endpoints.

    GET  /api/v1/learning/lessons                          → lesson catalog
    GET  /api/v1/learning/lessons/{slug}                   → full lesson
    GET  /api/v1/learning/lessons/{slug}/progress          → user progress
    POST /api/v1/learning/lessons/{slug}/sections/{sid}/complete
    POST /api/v1/learning/lessons/{slug}/answers           → validate answer

All progress/answer endpoints require authentication. Correct answers are
never serialized to clients; validation happens server-side and
deterministically. Since M26, lesson content is read from PostgreSQL through
the content repository; ``app.learning.content`` is the seed source that
populates it. Chemistry values referenced by lessons are served live from
ChemEngine via the existing element API (``chemistry_spotlight`` sections name
an element) and the existing chemistry explore API (sections name a molecule
by formula/SMILES/InChI).
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_db_session
from app.learning.content import Lesson, Question, Section
from app.models.learning import LessonProgress
from app.models.user import User
from app.services.learning import (
    LearningError,
    LearningService,
    recommend_next_lesson,
)

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
    objectives: list[str] = Field(default_factory=list)


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
    objectives: list[str] = Field(default_factory=list)
    sections: list[SectionPublic]


class LearningProgressResponse(BaseModel):
    """The authenticated user's progress in one lesson."""

    lesson_slug: str
    completed_sections: list[str]
    answers: dict[str, bool]
    progress_percent: int
    completed: bool


class ProgressListResponse(BaseModel):
    """The authenticated user's progress across all started lessons."""

    progress: list[LearningProgressResponse]


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


def _progress_response(progress: LessonProgress, lesson: Lesson) -> LearningProgressResponse:
    """Build the progress response, deriving percent from section counts."""
    total = len(lesson.sections)
    done = sum(1 for section in lesson.sections if section.id in progress.completed_sections)
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
        objectives=[*lesson.objectives],
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
                objectives=[*lesson.objectives],
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
    "/progress",
    response_model=ProgressListResponse,
    summary="List the user's progress across all lessons",
)
async def list_progress(
    service: Annotated[LearningService, Depends(get_learning_service)],
    user: Annotated[User, Depends(get_current_user)],
) -> ProgressListResponse:
    """Return progress for every lesson the user has started.

    Powers catalog "continue" badges so a returning student can resume where
    they left off. Progress rows for lessons that no longer exist or are no
    longer published are omitted — drafts stay invisible.
    """
    rows = await service.list_progress(user.id)
    # One query for the section ids of every published lesson; percent is
    # derived the same way as the per-lesson endpoint (_progress_response).
    sections_by_slug = {
        lesson.slug: [section.id for section in lesson.sections]
        for lesson in await service.list_lessons()
    }
    progress_responses: list[LearningProgressResponse] = []
    for row in rows:
        section_ids = sections_by_slug.get(row.lesson_slug)
        if section_ids is None:
            continue
        done = sum(1 for sid in section_ids if sid in row.completed_sections)
        percent = round(100 * done / len(section_ids)) if section_ids else 0
        progress_responses.append(
            LearningProgressResponse(
                lesson_slug=row.lesson_slug,
                completed_sections=list(row.completed_sections),
                answers=dict(row.answers),
                progress_percent=percent,
                completed=row.completed_at is not None,
            )
        )
    return ProgressListResponse(progress=progress_responses)


# --- Dashboard (M43) ---

# Earliest comparable timestamp so recently-drafted rows sort last deterministically.
_DASHBOARD_EPOCH = datetime.min.replace(tzinfo=timezone.utc)


class DashboardSectionProgress(BaseModel):
    """A started lesson as surfaced on the student dashboard."""

    lesson_slug: str
    title: str
    description: str
    subject: str
    difficulty: str
    estimated_minutes: int
    objectives: list[str] = Field(default_factory=list)
    progress_percent: int
    completed: bool
    completed_sections: list[str]
    section_count: int
    questions_attempted: int
    questions_correct: int
    needs_review: bool
    resume_section_id: str | None = None
    last_accessed_at: datetime | None = None


class DashboardTopicProgress(BaseModel):
    """Aggregate progress for a curricular subject."""

    subject: str
    lesson_count: int
    completed: int
    progress_percent: int


class DashboardTotals(BaseModel):
    """Roll-up counts for the dashboard."""

    started: int
    in_progress: int
    completed: int
    needs_review: int


class DashboardResponse(BaseModel):
    """Read-only dashboard view composed from the catalog + existing progress."""

    sections: list[DashboardSectionProgress]
    topics: list[DashboardTopicProgress]
    totals: DashboardTotals
    recommended_slug: str | None = None
    recommended_reason: str = ""
    recommended: DashboardSectionProgress | None = None


def _dashboard_section(
    lesson: Lesson, row: LessonProgress
) -> DashboardSectionProgress:
    """Project a progress row into the dashboard's per-lesson summary."""
    section_ids = [section.id for section in lesson.sections]
    done = sum(1 for sid in section_ids if sid in row.completed_sections)
    percent = round(100 * done / len(section_ids)) if section_ids else 0
    completed = row.completed_at is not None
    attempted = len(row.answers)
    correct = sum(1 for value in row.answers.values() if value)
    needs_review = attempted > 0 and correct < attempted
    resume_section_id: str | None = None
    if not completed:
        resume_section_id = next(
            (section.id for section in lesson.sections if section.id not in row.completed_sections),
            None,
        )
    return DashboardSectionProgress(
        lesson_slug=row.lesson_slug,
        title=lesson.title,
        description=lesson.description,
        subject=lesson.subject,
        difficulty=lesson.difficulty,
        estimated_minutes=lesson.estimated_minutes,
        objectives=[*lesson.objectives],
        progress_percent=percent,
        completed=completed,
        completed_sections=list(row.completed_sections),
        section_count=len(section_ids),
        questions_attempted=attempted,
        questions_correct=correct,
        needs_review=needs_review,
        resume_section_id=resume_section_id,
        last_accessed_at=row.updated_at,
    )


def _dashboard_response(
    lessons: list[Lesson], rows: list[LessonProgress]
) -> DashboardResponse:
    """Assemble the dashboard from the catalog and existing progress rows.

    Reuses the persisted ``LessonProgress`` rows (no new models). Progress rows
    for lessons that are no longer published are dropped, matching the catalog.
    """
    catalog_by_slug = {lesson.slug: lesson for lesson in lessons}
    progress_by_slug: dict[str, LessonProgress] = {}
    for row in rows:
        if row.lesson_slug in catalog_by_slug and row.lesson_slug not in progress_by_slug:
            progress_by_slug[row.lesson_slug] = row

    order_of = {lesson.slug: index for index, lesson in enumerate(lessons)}

    sections = [
        _dashboard_section(catalog_by_slug[row.lesson_slug], row)
        for row in progress_by_slug.values()
    ]
    # Most-recent activity first; stable for ties (earliest catalog order).
    sections.sort(
        key=lambda s: (
            -((s.last_accessed_at or _DASHBOARD_EPOCH).timestamp()),
            order_of.get(s.lesson_slug, len(lessons)),
        )
    )

    topic_map: dict[str, dict[str, int]] = {}
    topic_order: list[str] = []
    for lesson in lessons:
        topic = topic_map.setdefault(
            lesson.subject,
            {"lesson_count": 0, "section_total": 0, "section_done": 0, "completed": 0},
        )
        if lesson.subject not in topic_order:
            topic_order.append(lesson.subject)
        topic["lesson_count"] += 1
        section_ids = [section.id for section in lesson.sections]
        row = progress_by_slug.get(lesson.slug)
        if row is not None:
            done = sum(1 for sid in section_ids if sid in row.completed_sections)
            topic["section_total"] += len(section_ids)
            topic["section_done"] += done
            if row.completed_at is not None:
                topic["completed"] += 1

    topics = []
    for subject in topic_order:
        topic = topic_map[subject]
        topics.append(
            DashboardTopicProgress(
                subject=subject,
                lesson_count=topic["lesson_count"],
                completed=topic["completed"],
                progress_percent=(
                    round(100 * topic["section_done"] / topic["section_total"])
                    if topic["section_total"]
                    else 0
                ),
            )
        )

    totals = DashboardTotals(
        started=len(sections),
        in_progress=sum(1 for s in sections if not s.completed),
        completed=sum(1 for s in sections if s.completed),
        needs_review=sum(1 for s in sections if s.needs_review),
    )

    recommended_slug, recommended_reason = recommend_next_lesson(lessons, progress_by_slug)
    recommended: DashboardSectionProgress | None = None
    if recommended_slug is not None:
        rec_lesson = catalog_by_slug.get(recommended_slug)
        if rec_lesson is not None:
            recommended = DashboardSectionProgress(
                lesson_slug=rec_lesson.slug,
                title=rec_lesson.title,
                description=rec_lesson.description,
                subject=rec_lesson.subject,
                difficulty=rec_lesson.difficulty,
                estimated_minutes=rec_lesson.estimated_minutes,
                objectives=[*rec_lesson.objectives],
                progress_percent=0,
                completed=False,
                completed_sections=[],
                section_count=len(rec_lesson.sections),
                questions_attempted=0,
                questions_correct=0,
                needs_review=False,
                resume_section_id=rec_lesson.sections[0].id if rec_lesson.sections else None,
                last_accessed_at=None,
            )
    return DashboardResponse(
        sections=sections,
        topics=topics,
        totals=totals,
        recommended_slug=recommended_slug,
        recommended_reason=recommended_reason,
        recommended=recommended,
    )


@router.get(
    "/dashboard",
    response_model=DashboardResponse,
    summary="Student dashboard (continue-learning, topics, recommendation)",
)
async def get_dashboard(
    service: Annotated[LearningService, Depends(get_learning_service)],
    user: Annotated[User, Depends(get_current_user)],
) -> DashboardResponse:
    """Read-only dashboard view composed from the catalog and existing progress.

    The dashboard is a composition of existing data: the lesson catalog (M24) and
    the authenticated user's persisted progress rows (M28). No new progress
    models are introduced. ``recommended_slug`` is derived deterministically by
    ``recommend_next_lesson`` from catalog order and server-derived completion.
    """
    lessons = await service.list_lessons()
    rows = await service.list_progress(user.id)
    return _dashboard_response(lessons, rows)


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
