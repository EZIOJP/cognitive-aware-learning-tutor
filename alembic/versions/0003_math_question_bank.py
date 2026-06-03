"""Math question bank + attempt linkage.

Revision ID: 0003_math_bank
Revises: 0002_hub
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0003_math_bank"
down_revision: Union[str, None] = "0002_hub"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)

    if not insp.has_table("math_questions"):
        op.create_table(
            "math_questions",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("external_id", sa.String(80), nullable=True),
            sa.Column("topic", sa.String(80), nullable=False),
            sa.Column("prompt", sa.String(1000), nullable=False),
            sa.Column("expected_answer", sa.String(500), nullable=False),
            sa.Column("explanation", sa.Text(), nullable=True),
            sa.Column("latex", sa.Text(), nullable=True),
            sa.Column("difficulty", sa.String(20), nullable=True),
            sa.Column("answer_format", sa.String(40), nullable=True),
            sa.Column("tags_json", sa.Text(), nullable=True),
            sa.Column("metadata_json", sa.Text(), nullable=True),
            sa.Column("source", sa.String(40), nullable=True),
            sa.Column("is_active", sa.Boolean(), default=True),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.UniqueConstraint("topic", "external_id", name="uq_math_question_topic_external"),
        )
        op.create_index("ix_math_questions_topic", "math_questions", ["topic"])

    cols = [c["name"] for c in insp.get_columns("math_attempts")]
    if "question_id" not in cols:
        with op.batch_alter_table("math_attempts") as batch:
            batch.add_column(sa.Column("question_id", sa.Integer(), nullable=True))
            batch.add_column(sa.Column("generated_id", sa.String(36), nullable=True))
            batch.create_foreign_key(
                "fk_math_attempts_question_id",
                "math_questions",
                ["question_id"],
                ["id"],
                ondelete="SET NULL",
            )
    if "template_id" in cols:
        # Allow attempts from question bank without template
        with op.batch_alter_table("math_attempts") as batch:
            batch.alter_column("template_id", existing_type=sa.Integer(), nullable=True)


def downgrade() -> None:
    op.drop_table("math_questions")
    with op.batch_alter_table("math_attempts") as batch:
        batch.drop_column("generated_id")
        batch.drop_column("question_id")
