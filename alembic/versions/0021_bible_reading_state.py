"""Alembic: bible_reading_states for continue-where-you-left-off."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0021_bible_reading_state"
down_revision: Union[str, None] = "0020_journal_bible"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _insp():
    return sa.inspect(op.get_bind())


def upgrade() -> None:
    if not _insp().has_table("bible_reading_states"):
        op.create_table(
            "bible_reading_states",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("translation", sa.String(length=16), nullable=False),
            sa.Column("book_slug", sa.String(length=64), nullable=False),
            sa.Column("chapter", sa.Integer(), nullable=False),
            sa.Column("last_verse", sa.Integer(), nullable=True),
            sa.Column("chapters_per_day", sa.Integer(), nullable=False),
            sa.Column("chapters_completed", sa.Integer(), nullable=False),
            sa.Column("streak_days", sa.Integer(), nullable=False),
            sa.Column("last_completed_date", sa.String(length=10), nullable=True),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("user_id"),
        )
        with op.batch_alter_table("bible_reading_states", schema=None) as batch_op:
            batch_op.create_index(batch_op.f("ix_bible_reading_states_user_id"), ["user_id"], unique=True)


def downgrade() -> None:
    if _insp().has_table("bible_reading_states"):
        op.drop_table("bible_reading_states")
