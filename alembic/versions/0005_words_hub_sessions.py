"""Words table + hub session linkage on quiz and math.

Revision ID: 0005_words_hub
Revises: 0004_reconcile
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0005_words_hub"
down_revision: Union[str, None] = "0004_reconcile"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _insp():
    return sa.inspect(op.get_bind())


def _has_table(name: str) -> bool:
    return _insp().has_table(name)


def _has_column(table: str, col: str) -> bool:
    if not _has_table(table):
        return False
    return col in {c["name"] for c in _insp().get_columns(table)}


def upgrade() -> None:
    if not _has_table("words"):
        op.create_table(
            "words",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("word", sa.String(120), nullable=False),
            sa.Column("group_number", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("content_json", sa.Text(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=True),
        )
        op.create_index("ix_words_word", "words", ["word"])
        op.create_index("ix_words_group_number", "words", ["group_number"])

    if _has_table("quiz_sessions") and not _has_column("quiz_sessions", "hub_session_id"):
        op.add_column(
            "quiz_sessions",
            sa.Column("hub_session_id", sa.Integer(), nullable=True),
        )

    if _has_table("math_attempts") and not _has_column("math_attempts", "hub_session_id"):
        op.add_column(
            "math_attempts",
            sa.Column("hub_session_id", sa.Integer(), nullable=True),
        )


def downgrade() -> None:
    if _has_column("math_attempts", "hub_session_id"):
        op.drop_column("math_attempts", "hub_session_id")
    if _has_column("quiz_sessions", "hub_session_id"):
        op.drop_column("quiz_sessions", "hub_session_id")
    if _has_table("words"):
        op.drop_table("words")
