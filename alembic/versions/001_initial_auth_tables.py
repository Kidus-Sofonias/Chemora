"""Initial auth tables — users and sessions.

Revision ID: 001_initial_auth
Revises: None
Create Date: 2026-09-11

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

# revision identifiers, used by Alembic.
revision: str = "001_initial_auth"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create users and sessions tables."""
    # Users table
    op.create_table(
        "users",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "google_subject",
            sa.String(255),
            nullable=False,
            unique=True,
            comment="Google 'sub' — stable external identity",
        ),
        sa.Column(
            "email",
            sa.String(320),
            nullable=False,
            comment="Verified email from Google token",
        ),
        sa.Column(
            "display_name",
            sa.String(255),
            nullable=True,
            comment="Display name from Google profile",
        ),
        sa.Column(
            "avatar_url",
            sa.Text,
            nullable=True,
            comment="Avatar URL from Google profile",
        ),
        sa.Column(
            "last_login_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="Timestamp of most recent login",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    # Index on google_subject (already unique, but explicit for clarity)
    op.create_index("ix_users_google_subject", "users", ["google_subject"])

    # Index on email for lookups
    op.create_index("ix_users_email", "users", ["email"])

    # Sessions table
    op.create_table(
        "sessions",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "user_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "expires_at",
            sa.DateTime(timezone=True),
            nullable=False,
            comment="Absolute session expiry time",
        ),
        sa.Column(
            "last_activity_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
            comment="Last activity timestamp for inactivity tracking",
        ),
        sa.Column(
            "revoked_at",
            sa.DateTime(timezone=True),
            nullable=True,
            comment="When the session was revoked",
        ),
    )

    # Indexes for session lookup performance
    op.create_index("ix_sessions_user_id", "sessions", ["user_id"])
    op.create_index("ix_sessions_expires_at", "sessions", ["expires_at"])
    op.create_index(
        "ix_sessions_active",
        "sessions",
        ["user_id", "revoked_at", "expires_at"],
    )


def downgrade() -> None:
    """Drop sessions and users tables."""
    op.drop_table("sessions")
    op.drop_table("users")
