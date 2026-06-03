"""Baseline — existing vocab/math tables (may already exist from create_all).

Revision ID: 0001_baseline
Revises:
Create Date: 2026-06-02

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0001_baseline"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if insp.has_table("users"):
        return

    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("username", sa.String(80), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("password_plain", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("is_admin", sa.Boolean(), nullable=True),
    )
    op.create_index("ix_users_username", "users", ["username"], unique=True)

    op.create_table(
        "word_progress",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("word_id", sa.Integer(), nullable=False),
        sa.Column("mastery", sa.Integer(), default=0),
        sa.Column("times_asked", sa.Integer(), default=0),
        sa.Column("times_correct", sa.Integer(), default=0),
        sa.Column("consecutive_correct", sa.Integer(), default=0),
        sa.Column("due_date", sa.DateTime(), nullable=True),
        sa.Column("interval_days", sa.Integer(), default=0),
        sa.Column("is_suspended", sa.Boolean(), default=False),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("user_id", "word_id", name="uq_user_word"),
    )

    op.create_table(
        "math_question_templates",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("title", sa.String(160), nullable=False),
        sa.Column("topic", sa.String(80), nullable=True),
        sa.Column("operation", sa.String(40), nullable=True),
        sa.Column("min_value", sa.Integer(), nullable=True),
        sa.Column("max_value", sa.Integer(), nullable=True),
        sa.Column("number_type", sa.String(20), nullable=True),
        sa.Column("decimal_places", sa.Integer(), nullable=True),
        sa.Column("points", sa.Integer(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )

    op.create_table(
        "math_attempts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("template_id", sa.Integer(), sa.ForeignKey("math_question_templates.id")),
        sa.Column("topic", sa.String(80), nullable=True),
        sa.Column("prompt", sa.String(500), nullable=True),
        sa.Column("expected_answer", sa.String(160), nullable=True),
        sa.Column("user_answer", sa.String(160), nullable=True),
        sa.Column("is_correct", sa.Boolean(), nullable=True),
        sa.Column("mastery_delta", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("math_attempts")
    op.drop_table("math_question_templates")
    op.drop_table("word_progress")
    op.drop_table("users")
