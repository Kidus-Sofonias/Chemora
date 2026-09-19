"""Tutor conversation tables (M30).

Revision ID: 004_tutor_conversations
Revises: 003_content_tables
Create Date: 2026-09-19

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

# revision identifiers, used by Alembic.
revision: str = "004_tutor_conversations"
down_revision: Union[str, None] = "003_content_tables"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create the tutor_conversations and tutor_messages tables."""
    op.create_table(
        "tutor_conversations",
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
        sa.Column("title", sa.String(200), nullable=False, server_default=""),
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
    op.create_index(
        "ix_tutor_conversations_user_updated",
        "tutor_conversations",
        ["user_id", "updated_at"],
    )

    op.create_table(
        "tutor_messages",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "conversation_id",
            UUID(as_uuid=True),
            sa.ForeignKey(
                "tutor_conversations.id", ondelete="CASCADE"
            ),
            nullable=False,
        ),
        sa.Column("role", sa.String(16), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("seq", sa.Integer(), nullable=False, server_default="0"),
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
    op.create_index(
        "ix_tutor_messages_conversation_seq",
        "tutor_messages",
        ["conversation_id", "seq"],
    )
    op.create_index(
        op.f("ix_tutor_messages_conversation_id"),
        "tutor_messages",
        ["conversation_id"],
    )


def downgrade() -> None:
    """Drop the tutor conversation tables."""
    op.drop_index(
        op.f("ix_tutor_messages_conversation_id"), table_name="tutor_messages"
    )
    op.drop_index(
        "ix_tutor_messages_conversation_seq", table_name="tutor_messages"
    )
    op.drop_table("tutor_messages")
    op.drop_index(
        "ix_tutor_conversations_user_updated", table_name="tutor_conversations"
    )
    op.drop_table("tutor_conversations")
