"""Add app classification tables and audit columns on tracked_sessions."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0022_app_classification"
down_revision: Union[str, None] = "0021_bible_reading_state"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _insp():
    return sa.inspect(op.get_bind())


def upgrade() -> None:
    if not _insp().has_table("app_classification_suggestions"):
        op.create_table(
            "app_classification_suggestions",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("key", sa.String(), nullable=False),
            sa.Column("key_type", sa.String(), nullable=False),
            sa.Column("suggested_category", sa.String(), nullable=False),
            sa.Column("confidence", sa.Integer(), server_default="0"),
            sa.Column("sample_titles", sa.Text(), nullable=True),
            sa.Column("occurrence_count", sa.Integer(), server_default="1"),
            sa.Column("status", sa.String(), server_default="'pending'"),
            sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_app_classification_suggestions_key", "app_classification_suggestions", ["key"])

    if not _insp().has_table("app_classification_cache"):
        op.create_table(
            "app_classification_cache",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("key", sa.String(), nullable=False),
            sa.Column("key_type", sa.String(), nullable=False),
            sa.Column("category", sa.String(), nullable=False),
            sa.Column("source", sa.String(), server_default="'llm_reviewed'"),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_app_classification_cache_key", "app_classification_cache", ["key"], unique=True)

    if _insp().has_table("tracked_sessions"):
        cols = {c["name"] for c in _insp().get_columns("tracked_sessions")}
        if "category_source" not in cols:
            with op.batch_alter_table("tracked_sessions") as batch_op:
                batch_op.add_column(sa.Column("category_source", sa.String(), nullable=True))
        if "category_before_llm" not in cols:
            with op.batch_alter_table("tracked_sessions") as batch_op:
                batch_op.add_column(sa.Column("category_before_llm", sa.String(), nullable=True))


def downgrade() -> None:
    if _insp().has_table("tracked_sessions"):
        cols = {c["name"] for c in _insp().get_columns("tracked_sessions")}
        if "category_before_llm" in cols:
            with op.batch_alter_table("tracked_sessions") as batch_op:
                batch_op.drop_column("category_before_llm")
        if "category_source" in cols:
            with op.batch_alter_table("tracked_sessions") as batch_op:
                batch_op.drop_column("category_source")
    if _insp().has_table("app_classification_cache"):
        op.drop_table("app_classification_cache")
    if _insp().has_table("app_classification_suggestions"):
        op.drop_table("app_classification_suggestions")
