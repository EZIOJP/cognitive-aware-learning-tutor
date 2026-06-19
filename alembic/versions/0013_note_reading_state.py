"""Reading position + bookmark columns on lecture_notes."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0013_note_reading_state"
down_revision: Union[str, None] = "0012_note_library"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _insp():
    return sa.inspect(op.get_bind())


def _has_column(table: str, col: str) -> bool:
    if not _insp().has_table(table):
        return False
    return col in {c["name"] for c in _insp().get_columns(table)}


def upgrade() -> None:
    if not _has_column("lecture_notes", "read_scroll_top"):
        with op.batch_alter_table("lecture_notes") as batch:
            batch.add_column(sa.Column("read_scroll_top", sa.Integer(), server_default="0", nullable=False))
            batch.add_column(sa.Column("bookmark_scroll_top", sa.Integer(), nullable=True))
            batch.add_column(sa.Column("updated_at", sa.Integer(), nullable=True))


def downgrade() -> None:
    if _has_column("lecture_notes", "read_scroll_top"):
        with op.batch_alter_table("lecture_notes") as batch:
            batch.drop_column("updated_at")
            batch.drop_column("bookmark_scroll_top")
            batch.drop_column("read_scroll_top")
