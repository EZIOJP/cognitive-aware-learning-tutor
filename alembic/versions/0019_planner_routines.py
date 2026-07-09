"""Add planner_routines for persistent daily blocks."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0019_planner_routines"
down_revision: Union[str, None] = "0018_tracked_session_window_title"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _insp():
    return sa.inspect(op.get_bind())


def upgrade() -> None:
    if _insp().has_table("planner_routines"):
        return
    op.create_table(
        "planner_routines",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("category", sa.String(), nullable=False, server_default="personal"),
        sa.Column("start_time", sa.String(), nullable=False),
        sa.Column("end_time", sa.String(), nullable=True),
        sa.Column("duration_minutes", sa.Integer(), nullable=True),
        sa.Column("days_json", sa.Text(), nullable=False),
        sa.Column("color", sa.String(), nullable=True),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("planner_routines", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_planner_routines_user_id"), ["user_id"], unique=False)


def downgrade() -> None:
    if _insp().has_table("planner_routines"):
        op.drop_table("planner_routines")
