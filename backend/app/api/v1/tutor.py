"""AI chemistry tutor API (M29 + M30).

    POST /api/v1/learning/tutor — ask the chemistry tutor a question (M29,
    stateless).

M30 conversation infrastructure (all session-gated, ownership enforced):

    POST   /api/v1/learning/tutor/conversations              — create
    GET    /api/v1/learning/tutor/conversations              — list mine
    GET    /api/v1/learning/tutor/conversations/{id}         — messages
    DELETE /api/v1/learning/tutor/conversations/{id}         — delete
    POST   /api/v1/learning/tutor/conversations/{id}/messages — ask + stream

Authentication: the existing Chemora session cookie. Identity comes from the
server-side session — no client-supplied user id or ownership field is ever
trusted. Provider API keys never leave the server; responses contain only the
tutor's answer plus opaque metadata (lesson slugs and allowlisted tool names
used). The streaming endpoint emits Server-Sent Events with stable event
frames and never exposes provider tool traffic or internal prompts.
"""

from __future__ import annotations

import json
import logging
import uuid
from collections.abc import AsyncIterator
from typing import Annotated, Literal, cast

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
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
    CONVERSATION_LIMIT,
    CONVERSATION_NOT_FOUND,
    INVALID_MESSAGE,
    MAX_MESSAGE_CHARS,
    MESSAGE_LIMIT,
    RATE_LIMITED,
    ConversationSummary,
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
    CONVERSATION_NOT_FOUND: 404,
    CONVERSATION_LIMIT: 409,
    MESSAGE_LIMIT: 409,
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


# ── M30: conversations ──────────────────────────────────────────────


class ConversationCreateRequest(BaseModel):
    """Request body for creating a conversation (title optional)."""

    title: str | None = Field(default=None, max_length=200)


class ConversationSummaryResponse(BaseModel):
    """Client-safe conversation metadata (never the messages)."""

    id: uuid.UUID
    title: str
    created_at: str
    updated_at: str
    message_count: int


class ConversationListResponse(BaseModel):
    """The authenticated user's conversations, most recent first."""

    conversations: list[ConversationSummaryResponse]


class ConversationMessageResponse(BaseModel):
    """One persisted message (user/assistant text only)."""

    role: Literal["user", "assistant"]
    content: str


class ConversationDetailResponse(BaseModel):
    """A conversation's id and its messages in order."""

    id: uuid.UUID
    title: str
    messages: list[ConversationMessageResponse]


class ConversationDeleteResponse(BaseModel):
    """Result of a conversation deletion."""

    deleted: bool


class ConversationMessageRequest(BaseModel):
    """Body for asking a question inside a conversation (streamed)."""

    message: str = Field(min_length=1, max_length=MAX_MESSAGE_CHARS)
    lesson_slug: str | None = Field(default=None, max_length=200)


def _summary_response(row: object) -> ConversationSummaryResponse:
    """Map a service ConversationSummary to its response model."""
    summary = cast("ConversationSummary", row)
    return ConversationSummaryResponse(
        id=summary.id,
        title=summary.title,
        created_at=summary.created_at.isoformat(),
        updated_at=summary.updated_at.isoformat(),
        message_count=summary.message_count,
    )


@router.post(
    "/tutor/conversations",
    response_model=ConversationSummaryResponse,
    status_code=201,
    summary="Create a tutor conversation",
    responses={401: {"model": TutorErrorDetail}},
)
async def create_conversation(
    request: ConversationCreateRequest,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> ConversationSummaryResponse:
    """Create an empty conversation owned by the authenticated user."""
    service = TutorService(db)
    try:
        summary = await service.create_conversation(user.id, request.title)
    except TutorError as exc:
        raise HTTPException(
            status_code=_STATUS_BY_CODE.get(exc.code, 500),
            detail={"code": exc.code, "message": exc.message},
        ) from exc
    return _summary_response(summary)


@router.get(
    "/tutor/conversations",
    response_model=ConversationListResponse,
    summary="List my tutor conversations",
    responses={401: {"model": TutorErrorDetail}},
)
async def list_conversations(
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> ConversationListResponse:
    """List the authenticated user's conversations (metadata only)."""
    service = TutorService(db)
    rows = await service.list_conversations(user.id)
    return ConversationListResponse(
        conversations=[_summary_response(row) for row in rows]
    )


@router.get(
    "/tutor/conversations/{conversation_id}",
    response_model=ConversationDetailResponse,
    summary="Get one conversation's messages",
    responses={
        401: {"model": TutorErrorDetail},
        404: {"model": TutorErrorDetail, "description": "Not found or not yours"},
    },
)
async def get_conversation(
    conversation_id: uuid.UUID,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> ConversationDetailResponse:
    """Return one conversation's messages (ownership enforced).

    Another user's conversation is indistinguishable from a missing one.
    """
    service = TutorService(db)
    try:
        messages = await service.get_conversation_messages(user.id, conversation_id)
    except TutorError as exc:
        raise HTTPException(
            status_code=_STATUS_BY_CODE.get(exc.code, 500),
            detail={"code": exc.code, "message": exc.message},
        ) from exc
    return ConversationDetailResponse(
        id=conversation_id,
        title="",
        messages=[
            ConversationMessageResponse(
                role=cast("Literal['user', 'assistant']", m["role"]),
                content=m["content"],
            )
            for m in messages
        ],
    )


@router.delete(
    "/tutor/conversations/{conversation_id}",
    response_model=ConversationDeleteResponse,
    summary="Delete one of my conversations",
    responses={
        401: {"model": TutorErrorDetail},
        404: {"model": TutorErrorDetail, "description": "Not found or not yours"},
    },
)
async def delete_conversation(
    conversation_id: uuid.UUID,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> ConversationDeleteResponse:
    """Delete a conversation (messages cascade). Ownership enforced."""
    service = TutorService(db)
    deleted = await service.delete_conversation(user.id, conversation_id)
    if not deleted:
        raise HTTPException(
            status_code=404,
            detail={
                "code": CONVERSATION_NOT_FOUND,
                "message": "That conversation could not be found.",
            },
        )
    return ConversationDeleteResponse(deleted=True)


@router.post(
    "/tutor/conversations/{conversation_id}/messages",
    summary="Ask a question in a conversation (streamed answer)",
    responses={
        401: {"model": TutorErrorDetail},
        404: {"model": TutorErrorDetail, "description": "Not found or not yours"},
        422: {"model": TutorErrorDetail},
        429: {"model": TutorErrorDetail},
    },
)
async def ask_conversation_stream(
    conversation_id: uuid.UUID,
    request: ConversationMessageRequest,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> StreamingResponse:
    """Ask inside a conversation and stream the answer as Server-Sent Events.

    Event frames (one JSON object per ``data:`` line):
        {"type": "delta", "text": "..."}
        {"type": "done", "tools_used": [...], "lesson_slugs": [...]}
        {"type": "error", "code": "...", "message": "..."}

    Ownership, validation, rate limiting, and persistence happen before/while
    streaming; the streamed answer is persisted even if the client
    disconnects mid-stream.
    """
    service = TutorService(db)

    # Validate ownership/limits up-front so a real HTTP status is returned
    # before the streaming response starts.
    try:
        await service.assert_conversation(user.id, conversation_id)
        text = TutorService._validate_message(request.message)
        service._limiter.check(user.id)  # noqa: SLF001 - pre-flight check
    except TutorError as exc:
        raise HTTPException(
            status_code=_STATUS_BY_CODE.get(exc.code, 500),
            detail={"code": exc.code, "message": exc.message},
        ) from exc
    del text  # validated pre-flight; the stream re-validates defensively

    async def event_stream() -> AsyncIterator[str]:
        """Encode tutor stream events as Server-Sent Events."""
        try:
            async for event in service.stream_in_conversation(
                user.id,
                conversation_id,
                request.message,
                request.lesson_slug,
                check_limiter=False,  # limiter already checked pre-flight
            ):
                yield f"data: {json.dumps(event, default=str)}\n\n"
        except TutorError as exc:
            yield (
                "data: "
                + json.dumps(
                    {"type": "error", "code": exc.code, "message": exc.message}
                )
                + "\n\n"
            )
        except Exception:  # noqa: BLE001 - never leak internals to the client
            logger.exception("Unexpected streaming tutor failure")
            yield (
                "data: "
                + json.dumps(
                    {
                        "type": "error",
                        "code": AI_ERROR,
                        "message": "The tutor hit a problem. Please try again.",
                    }
                )
                + "\n\n"
            )

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
