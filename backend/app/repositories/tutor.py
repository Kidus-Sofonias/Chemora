"""Tutor conversation repository — persistence for tutoring history (M30).

The repository owns every SQLAlchemy query for tutor conversations so that
neither route handlers nor services touch the database directly (same layering
as :mod:`app.repositories.content`):

    Route → TutorService → TutorConversationRepository → SQLAlchemy

**Ownership boundary.** Every query takes the owning ``user_id`` and filters
by it. A conversation id that exists but belongs to another user is
indistinguishable from a missing one (404), which is the safest way to avoid
leaking the existence of other users' conversations.

**Limits.** ``MAX_CONVERSATIONS_PER_USER`` bounds storage per student: when
the cap is reached, creation of a new conversation is refused by the service
until an old one is deleted. Message count per conversation is bounded
similarly. Limits are deliberately conservative and enforced in the
repository so they hold regardless of the caller.
"""

from __future__ import annotations

import uuid

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.tutor import TutorConversation, TutorMessage

#: Maximum conversations retained per user (oldest can be deleted to make room).
MAX_CONVERSATIONS_PER_USER = 30
#: Maximum messages retained per conversation.
MAX_MESSAGES_PER_CONVERSATION = 200


class TutorConversationRepository:
    """Data-access layer for tutor conversations (ownership-checked)."""

    def __init__(self, db: AsyncSession) -> None:
        """Initialize with the request's database session."""
        self._db = db

    # ── Reads ─────────────────────────────────────────────────────────

    async def count_for_user(self, user_id: uuid.UUID) -> int:
        """Count the conversations owned by a user."""
        result = await self._db.execute(
            select(func.count())
            .select_from(TutorConversation)
            .where(TutorConversation.user_id == user_id)
        )
        return int(result.scalar_one())

    async def get_conversation(
        self, conversation_id: uuid.UUID, user_id: uuid.UUID
    ) -> TutorConversation | None:
        """Return the conversation only when it exists AND belongs to the user."""
        result = await self._db.execute(
            select(TutorConversation)
            .where(
                TutorConversation.id == conversation_id,
                TutorConversation.user_id == user_id,
            )
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def list_conversations(
        self, user_id: uuid.UUID, *, limit: int = 50
    ) -> list[TutorConversation]:
        """List a user's conversations, most recently active first."""
        result = await self._db.execute(
            select(TutorConversation)
            .where(TutorConversation.user_id == user_id)
            .order_by(TutorConversation.updated_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def list_messages(
        self, conversation_id: uuid.UUID, *, limit: int | None = None
    ) -> list[TutorMessage]:
        """Return a conversation's messages in insertion order.

        The caller must have already verified ownership of the conversation.
        When ``limit`` is given, the most recent ``limit`` messages are
        returned in chronological order.
        """
        stmt = (
            select(TutorMessage)
            .where(TutorMessage.conversation_id == conversation_id)
            .order_by(TutorMessage.seq.asc())
        )
        if limit is not None:
            stmt = stmt.order_by(TutorMessage.seq.desc()).limit(limit)
            # Re-wrap: order most-recent-first for the limit, then restore
            # chronological order in Python.
            rows = list(
                (
                    await self._db.execute(stmt)
                ).scalars().all()[::-1],
            )
            return rows
        rows = list((await self._db.execute(stmt)).scalars().all())
        return rows

    # ── Writes ────────────────────────────────────────────────────────

    async def create_conversation(
        self, user_id: uuid.UUID, title: str
    ) -> TutorConversation:
        """Create a conversation for the user (cap enforced)."""
        count = await self.count_for_user(user_id)
        if count >= MAX_CONVERSATIONS_PER_USER:
            raise ConversationLimitError(
                "conversation_limit",
                f"You have reached the limit of {MAX_CONVERSATIONS_PER_USER} "
                "conversations. Delete one to start a new chat.",
            )
        conversation = TutorConversation(user_id=user_id, title=title[:200])
        self._db.add(conversation)
        await self._db.flush()
        return conversation

    async def append_message(
        self,
        conversation: TutorConversation,
        role: str,
        content: str,
    ) -> TutorMessage:
        """Append one message to a conversation (message cap enforced).

        Bumps the conversation's ``updated_at`` so recency ordering works.
        """
        if role not in ("user", "assistant"):
            raise ValueError(f"Invalid message role: {role!r}")
        count = await self.count_messages(conversation.id)
        if count >= MAX_MESSAGES_PER_CONVERSATION:
            raise ConversationLimitError(
                "message_limit",
                "This conversation is full. Please start a new chat.",
            )
        seq = count  # messages are append-only; count == next zero-based seq
        message = TutorMessage(
            conversation_id=conversation.id,
            role=role,
            content=content,
            seq=seq,
        )
        self._db.add(message)
        # Touch the parent so TIMESTAMP onupdate fires.
        conversation.title = conversation.title
        await self._db.flush()
        return message

    async def count_messages(self, conversation_id: uuid.UUID) -> int:
        """Count the messages in a conversation."""
        result = await self._db.execute(
            select(func.count())
            .select_from(TutorMessage)
            .where(TutorMessage.conversation_id == conversation_id)
        )
        return int(result.scalar_one())

    async def delete_conversation(
        self, conversation_id: uuid.UUID, user_id: uuid.UUID
    ) -> bool:
        """Delete a conversation only when it belongs to the user.

        Messages are removed by the database-level ON DELETE CASCADE (and by
        the ORM cascade when the relationship is loaded). Returns True when a
        row was deleted, False when no owned conversation matched.
        """
        result = await self._db.execute(
            delete(TutorConversation)
            .where(
                TutorConversation.id == conversation_id,
                TutorConversation.user_id == user_id,
            )
            .execution_options(synchronize_session=False)
        )
        return bool(getattr(result, "rowcount", 0))

    async def delete_all_for_user(self, user_id: uuid.UUID) -> int:
        """Delete every conversation owned by a user. Returns rows deleted."""
        result = await self._db.execute(
            delete(TutorConversation)
            .where(TutorConversation.user_id == user_id)
            .execution_options(synchronize_session=False)
        )
        return int(getattr(result, "rowcount", 0) or 0)


class ConversationLimitError(Exception):
    """A stable, client-safe limit violation."""

    def __init__(self, code: str, message: str) -> None:
        """Initialize with a stable code and user-facing message."""
        super().__init__(message)
        self.code = code
        self.message = message
