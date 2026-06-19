"""Study library folders — folder_path, kind, relative_path on lecture_notes."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0012_note_library"
down_revision: Union[str, None] = "0011_focus_notes"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _insp():
    return sa.inspect(op.get_bind())


def _has_column(table: str, col: str) -> bool:
    if not _insp().has_table(table):
        return False
    return col in {c["name"] for c in _insp().get_columns(table)}


def upgrade() -> None:
    if not _has_column("lecture_notes", "folder_path"):
        with op.batch_alter_table("lecture_notes") as batch:
            batch.add_column(sa.Column("folder_path", sa.String(512), server_default="", nullable=False))
            batch.add_column(sa.Column("kind", sa.String(32), server_default="lecture", nullable=False))
            batch.add_column(sa.Column("relative_path", sa.String(512), nullable=True))
        op.create_index("ix_lecture_notes_folder_path", "lecture_notes", ["folder_path"])
        op.create_index("ix_lecture_notes_kind", "lecture_notes", ["kind"])

    conn = op.get_bind()
    conn.execute(
        sa.text(
            "UPDATE lecture_notes SET relative_path = filename WHERE relative_path IS NULL OR relative_path = ''"
        )
    )


def downgrade() -> None:
    if _has_column("lecture_notes", "folder_path"):
        op.drop_index("ix_lecture_notes_kind", table_name="lecture_notes")
        op.drop_index("ix_lecture_notes_folder_path", table_name="lecture_notes")
        with op.batch_alter_table("lecture_notes") as batch:
            batch.drop_column("relative_path")
            batch.drop_column("kind")
            batch.drop_column("folder_path")
