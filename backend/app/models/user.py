"""User and Session database models.

The Google `sub` value is the stable external identity identifier.
Email is NOT the primary identity key.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Index, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, generate_uuid


class User(Base, TimestampMixin):
    """Chemora user.

    Identity is based on Google's stable `sub` identifier, NOT email.
    Email can change; Google sub is unique per Google account.
    """

    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=generate_uuid,
    )
    google_subject: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        nullable=False,
        index=True,
        comment="Google 'sub' — stable external identity",
    )
    email: Mapped[str] = mapped_column(
        String(320),
        nullable=False,
        comment="Verified email from Google token",
    )
    display_name: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        comment="Display name from Google profile",
    )
    avatar_url: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Avatar URL from Google profile",
    )
    last_login_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Timestamp of most recent login",
    )

    # Relationships
    sessions: Mapped[list[Session]] = relationship(
        "Session",
        back_populates="user",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        Index("ix_users_email", "email"),
    )

    def __repr__(self) -> str:
        """Return string representation without sensitive data."""
        return f"<User id={self.id} google_subject=***>"


class Session(Base):
    """Chemora session.

    Tracks active authentication sessions with expiration and
    inactivity timeout support.
    """

    __tablename__ = "sessions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=generate_uuid,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        comment="Absolute session expiry time",
    )
    last_activity_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        comment="Last activity timestamp for inactivity tracking",
    )
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="When the session was revoked (logout or admin action)",
    )

    # Relationships
    user: Mapped[User] = relationship(
        "User",
        back_populates="sessions",
    )

    __table_args__ = (
        Index("ix_sessions_expires_at", "expires_at"),
        Index("ix_sessions_active", "user_id", "revoked_at", "expires_at"),
    )

    @property
    def is_active(self) -> bool:
        """Check if session is currently active (not revoked and not expired).

        Returns:
            True if session is active.
        """
        now = datetime.now(timezone.utc)
        if self.revoked_at is not None:
            return False
        expires_at = self.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        return expires_at > now

    def __repr__(self) -> str:
        """Return string representation without sensitive data."""
        return f"<Session id={self.id} user_id={self.user_id}>"
