"""Content tables for the database-backed CMS, plus the admin flag (M26).

Revision ID: 003_content_tables
Revises: 002_lesson_progress
Create Date: 2026-09-18

Creates:

- ``users.is_admin`` — content-management authorization flag
- ``lessons`` — lesson metadata, ordering and publication state
- ``lesson_sections`` — ordered sections, including chemistry references
- ``lesson_questions`` — questions with the server-only answer key

``lesson_progress.lesson_slug`` keeps referencing the lesson slug, so existing
progress rows stay valid; slugs are the stable key carried over from the seed
layer.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

# revision identifiers, used by Alembic.
revision: str = "003_content_tables"
down_revision: Union[str, None] = "002_lesson_progress"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add the admin flag and the content tables."""
    op.add_column(
        "users",
        sa.Column(
            "is_admin",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
            comment="Content-management authorization (M26)",
        ),
    )

    op.create_table(
        "lessons",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("slug", sa.String(100), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("topic", sa.String(100), nullable=False),
        sa.Column("difficulty", sa.String(20), nullable=False),
        sa.Column("estimated_minutes", sa.Integer(), nullable=False),
        sa.Column("ordering", sa.Integer(), nullable=False),
        sa.Column(
            "published",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint("slug", name="uq_lessons_slug"),
    )
    op.create_index("ix_lessons_slug", "lessons", ["slug"])
    op.create_index("ix_lessons_ordering", "lessons", ["ordering"])
    op.create_index("ix_lessons_published", "lessons", ["published"])

    op.create_table(
        "lesson_sections",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "lesson_id",
            UUID(as_uuid=True),
            sa.ForeignKey("lessons.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("section_id", sa.String(50), nullable=False),
        sa.Column("kind", sa.String(30), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("body", sa.JSON(), nullable=False),
        sa.Column("element_symbol", sa.String(10), nullable=True),
        sa.Column("molecule_input", sa.String(200), nullable=True),
        sa.Column("ordering", sa.Integer(), nullable=False),
        sa.UniqueConstraint("lesson_id", "section_id", name="uq_section_lesson_id"),
    )
    op.create_index(
        "ix_lesson_sections_lesson", "lesson_sections", ["lesson_id", "ordering"]
    )

    op.create_table(
        "lesson_questions",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "lesson_id",
            UUID(as_uuid=True),
            sa.ForeignKey("lessons.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("section_id", sa.String(50), nullable=False),
        sa.Column("question_id", sa.String(50), nullable=False),
        sa.Column("kind", sa.String(20), nullable=False),
        sa.Column("prompt", sa.Text(), nullable=False),
        sa.Column("correct", sa.Text(), nullable=False),
        sa.Column("explanation", sa.Text(), nullable=False),
        sa.Column("options", sa.JSON(), nullable=False),
        sa.Column("ordering", sa.Integer(), nullable=False),
        sa.UniqueConstraint("lesson_id", "question_id", name="uq_question_lesson_id"),
        sa.ForeignKeyConstraint(
            ["lesson_id", "section_id"],
            ["lesson_sections.lesson_id", "lesson_sections.section_id"],
            ondelete="CASCADE",
            name="fk_question_section",
        ),
    )
    op.create_index(
        "ix_lesson_questions_lesson", "lesson_questions", ["lesson_id", "ordering"]
    )


def downgrade() -> None:
    """Remove the content tables and the admin flag."""
    op.drop_index("ix_lesson_questions_lesson", table_name="lesson_questions")
    op.drop_table("lesson_questions")
    op.drop_index("ix_lesson_sections_lesson", table_name="lesson_sections")
    op.drop_table("lesson_sections")
    op.drop_index("ix_lessons_published", table_name="lessons")
    op.drop_index("ix_lessons_ordering", table_name="lessons")
    op.drop_index("ix_lessons_slug", table_name="lessons")
    op.drop_table("lessons")
    op.drop_column("users", "is_admin")