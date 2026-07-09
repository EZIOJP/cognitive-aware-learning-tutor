"""Alembic: bible_reading_logs + journal_entries."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0020_journal_bible"
down_revision: Union[str, None] = "0019_planner_routines"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _insp():
    return sa.inspect(op.get_bind())


def upgrade() -> None:
    if not _insp().has_table("bible_reading_logs"):
        op.create_table(
            "bible_reading_logs",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("read_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("passage", sa.String(length=512), nullable=False),
            sa.Column("translation", sa.String(length=64), nullable=True),
            sa.Column("duration_minutes", sa.Integer(), nullable=True),
            sa.Column("reflection", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
        with op.batch_alter_table("bible_reading_logs", schema=None) as batch_op:
            batch_op.create_index(batch_op.f("ix_bible_reading_logs_user_id"), ["user_id"], unique=False)

    if not _insp().has_table("journal_entries"):
        op.create_table(
            "journal_entries",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("entry_date", sa.String(length=10), nullable=False),
            sa.Column("title", sa.String(length=255), nullable=True),
            sa.Column("content", sa.Text(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
        with op.batch_alter_table("journal_entries", schema=None) as batch_op:
            batch_op.create_index(batch_op.f("ix_journal_entries_user_id"), ["user_id"], unique=False)
            batch_op.create_index(batch_op.f("ix_journal_entries_entry_date"), ["entry_date"], unique=False)


def downgrade() -> None:
    for table in ("journal_entries", "bible_reading_logs"):
        if _insp().has_table(table):
            op.drop_table(table)
