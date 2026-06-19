"""Focus events and lecture notes index — migration 0011."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0011_focus_notes"
down_revision: Union[str, None] = "0006_user_features"
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
    if not _has_column("users", "face_embedding_json"):
        with op.batch_alter_table("users") as batch:
            batch.add_column(sa.Column("face_embedding_json", sa.Text(), nullable=True))

    if not _has_table("focus_events"):
        op.create_table(
            "focus_events",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("session_id", sa.String(64), nullable=True),
            sa.Column("event_type", sa.String(32), nullable=False),
            sa.Column("duration_seconds", sa.Float(), nullable=True),
            sa.Column("pomodoro_mode", sa.String(16), nullable=False, server_default="focus"),
            sa.Column("started_at", sa.Integer(), nullable=False),
            sa.Column("ended_at", sa.Integer(), nullable=True),
        )
        op.create_index("ix_focus_events_user_id", "focus_events", ["user_id"])

    if not _has_table("lecture_notes"):
        op.create_table(
            "lecture_notes",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("filename", sa.String(255), nullable=False),
            sa.Column("title", sa.String(255), nullable=False),
            sa.Column("topic", sa.String(160), nullable=True),
            sa.Column("source", sa.String(32), server_default="manual", nullable=False),
            sa.Column("transcript_file", sa.String(255), nullable=True),
            sa.Column("section_count", sa.Integer(), server_default="0", nullable=False),
            sa.Column("created_at", sa.Integer(), nullable=False),
            sa.UniqueConstraint("filename", name="uq_lecture_notes_filename"),
        )
        op.create_index("ix_lecture_notes_user_id", "lecture_notes", ["user_id"])
        op.create_index("ix_lecture_notes_topic", "lecture_notes", ["topic"])


def downgrade() -> None:
    if _has_table("lecture_notes"):
        op.drop_table("lecture_notes")
    if _has_table("focus_events"):
        op.drop_table("focus_events")
    if _has_column("users", "face_embedding_json"):
        with op.batch_alter_table("users") as batch:
            batch.drop_column("face_embedding_json")
