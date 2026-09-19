"""Tutor conversation database models (M30).

Persistence for the AI chemistry tutor: a conversation groups the messages
exchanged between one student and the tutor. Design notes:

- Ownership is enforced at the storage layer: every query in
  ``app/repositories/tutor.py`` filters by ``user_id``, which is always
  derived from the server-side Chemora session (never from the client).
- Message ``role`` is limited to ``user`` / ``assistant`` — the internal
  system prompt and provider tool traffic are never persisted.
- ``content`` uses ``Text`` (the M26 convention for free prose) and message
  bodies are additionally length-bounded by the service layer before
  insertion, so the Text type is not an invitation to store unbounded data.
- Indexes follow the access patterns: list a user's conversations ordered by
  recency, and load one conversation's messages in insertion order.
"""

from __future__ import annotations

import uuid

from sqlalchemy import (
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, generate_uuid


class TutorConversation(Base, TimestampMixin):
    """One student's tutoring conversation."""

    __tablename__ = "tutor_conversations"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=generate_uuid,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False, default="")

    messages: Mapped[list[TutorMessage]] = relationship(
        back_populates="conversation",
        cascade="all, delete-orphan",
        order_by="TutorMessage.created_at",
        lazy="selectin",
    )

    __table_args__ = (
        Index("ix_tutor_conversations_user_updated", "user_id", "updated_at"),
    )

    def __repr__(self) -> str:
        """Return string representation without sensitive data."""
        return f"<TutorConversation id={self.id} user_id={self.user_id}>"


class TutorMessage(Base, TimestampMixin):
    """One message inside a tutoring conversation."""

    __tablename__ = "tutor_messages"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=generate_uuid,
    )
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tutor_conversations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # "user" or "assistant" — enforced by the repository/service layer.
    role: Mapped[str] = mapped_column(String(16), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    # Monotonic position within the conversation for deterministic ordering
    # even when two messages share a timestamp (bulk inserts).
    seq: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    conversation: Mapped[TutorConversation] = relationship(
        back_populates="messages",
    )

    __table_args__ = (
        Index("ix_tutor_messages_conversation_seq", "conversation_id", "seq"),
    )

    def __repr__(self) -> str:
        """Return string representation without sensitive data."""
        return (
            f"<TutorMessage conversation_id={self.conversation_id} "
            f"role={self.role} seq={self.seq}>"
        )
