"""Lesson learning objectives column (M42).

Revision ID: 005_lesson_objectives
Revises: 004_tutor_conversations
Create Date: 2026-09-29

Adds a JSON ``objectives`` column to ``lessons`` so lessons can carry
lesson-level learning objectives (curricular prose, never chemistry values).
The column defaults to an empty list, so existing rows remain valid.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "005_lesson_objectives"
down_revision: Union[str, None] = "004_tutor_conversations"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add the objectives column to lessons."""
    op.add_column(
        "lessons",
        sa.Column(
            "objectives",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'[]'"),
            comment="Lesson-level learning objectives (curricular prose)",
        ),
    )


def downgrade() -> None:
    """Remove the objectives column from lessons."""
    op.drop_column("lessons", "objectives")