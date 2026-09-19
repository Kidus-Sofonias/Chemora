"""AI chemistry tutor API (M29).

    POST /api/v1/learning/tutor — ask the chemistry tutor a question.

Authentication: the existing Chemora session cookie. Identity comes from the
server-side session — no client-supplied user id is ever trusted. Provider
API keys never leave the server; responses contain only the tutor's answer
plus opaque metadata (lesson slugs and allowlisted tool names used).
"""

from __future__ import annotations

import logging
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_db_session
from app.models.user import User
from app.services.ai.service import (
    AI_AUTH,
    AI_ERROR,
    AI_TIMEOUT,
    AI_UNAVAILABLE,
    INVALID_MESSAGE,
    MAX_MESSAGE_CHARS,
    RATE_LIMITED,
    TutorError,
    TutorService,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/learning", tags=["tutor"])

#: Status mapping for stable tutor error codes.
_STATUS_BY_CODE = {
    INVALID_MESSAGE: 422,
    RATE_LIMITED: 429,
    AI_TIMEOUT: 504,
    AI_UNAVAILABLE: 503,
    AI_AUTH: 500,
    AI_ERROR: 500,
}


class TutorTurn(BaseModel):
    """One prior conversation turn (untrusted client data)."""

    role: Literal["user", "assistant"] = "user"
    content: str = Field(default="", max_length=2000)


class TutorRequest(BaseModel):
    """Request body for a tutoring question."""

    message: str = Field(min_length=1, max_length=MAX_MESSAGE_CHARS)
    history: list[TutorTurn] = Field(default_factory=list, max_length=24)
    lesson_slug: str | None = Field(default=None, max_length=200)


class TutorResponse(BaseModel):
    """Tutor answer plus opaque metadata (no provider payloads)."""

    answer: str
    lesson_slugs: list[str]
    tools_used: list[str]


class TutorErrorDetail(BaseModel):
    """Stable machine-readable error code plus a user-facing message."""

    code: str
    message: str


@router.post(
    "/tutor",
    response_model=TutorResponse,
    summary="Ask the chemistry tutor",
    responses={
        401: {"model": TutorErrorDetail, "description": "Not authenticated"},
        422: {"model": TutorErrorDetail, "description": "Invalid message"},
        429: {"model": TutorErrorDetail, "description": "Too many requests"},
        500: {"model": TutorErrorDetail, "description": "Tutor failure"},
        503: {"model": TutorErrorDetail, "description": "AI service unavailable"},
        504: {"model": TutorErrorDetail, "description": "AI service timeout"},
    },
)
async def ask_tutor(
    request: TutorRequest,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> TutorResponse:
    """Answer one tutoring question for the authenticated student."""
    service = TutorService(db)
    try:
        result = await service.ask(
            user_id=user.id,
            message=request.message,
            history=[turn.model_dump() for turn in request.history],
            lesson_slug=request.lesson_slug,
        )
    except TutorError as exc:
        logger.info(
            "Tutor request failed with controlled error",
            extra={"code": exc.code},
        )
        raise HTTPException(
            status_code=_STATUS_BY_CODE.get(exc.code, 500),
            detail={"code": exc.code, "message": exc.message},
        ) from exc
    except Exception:  # noqa: BLE001 - never leak internals to the client
        logger.exception("Unexpected tutor failure")
        raise HTTPException(
            status_code=500,
            detail={
                "code": "ai_error",
                "message": "The tutor hit a problem. Please try again.",
            },
        ) from None
    return TutorResponse(
        answer=result.answer,
        lesson_slugs=result.lesson_slugs,
        tools_used=result.tools_used,
    )
