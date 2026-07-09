"""Add planner_blocks table for holistic calendar."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0017_planner_blocks"
down_revision: Union[str, None] = "0016_timetable_schedule"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _insp():
    return sa.inspect(op.get_bind())


def upgrade() -> None:
    if _insp().has_table("planner_blocks"):
        return
    op.create_table(
        "planner_blocks",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("category", sa.String(), nullable=False, server_default="study"),
        sa.Column("start_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("planned_minutes", sa.Integer(), nullable=False),
        sa.Column("remaining_minutes", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(), nullable=False, server_default="scheduled"),
        sa.Column("rolled_from_id", sa.Integer(), nullable=True),
        sa.Column("roll_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("task_id", sa.Integer(), nullable=True),
        sa.Column("color", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["rolled_from_id"], ["planner_blocks.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["task_id"], ["timetable_tasks.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_planner_blocks_user_id", "planner_blocks", ["user_id"])
    op.create_index("ix_planner_blocks_start_at", "planner_blocks", ["start_at"])


def downgrade() -> None:
    if _insp().has_table("planner_blocks"):
        op.drop_index("ix_planner_blocks_start_at", table_name="planner_blocks")
        op.drop_index("ix_planner_blocks_user_id", table_name="planner_blocks")
        op.drop_table("planner_blocks")
