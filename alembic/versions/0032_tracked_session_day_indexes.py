"""Indexes for tracked_sessions day-overlap queries (gate + rollup)."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0032_tracked_session_day_indexes"
down_revision: Union[str, None] = "0031_study_loop_days"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    insp = sa.inspect(op.get_bind())
    if not insp.has_table("tracked_sessions"):
        return
    existing = {ix["name"] for ix in insp.get_indexes("tracked_sessions")}
    if "ix_tracked_sessions_user_start" not in existing:
        op.create_index(
            "ix_tracked_sessions_user_start",
            "tracked_sessions",
            ["user_id", "start_time"],
        )
    if "ix_tracked_sessions_user_end" not in existing:
        op.create_index(
            "ix_tracked_sessions_user_end",
            "tracked_sessions",
            ["user_id", "end_time"],
        )


def downgrade() -> None:
    insp = sa.inspect(op.get_bind())
    if not insp.has_table("tracked_sessions"):
        return
    existing = {ix["name"] for ix in insp.get_indexes("tracked_sessions")}
    if "ix_tracked_sessions_user_end" in existing:
        op.drop_index("ix_tracked_sessions_user_end", table_name="tracked_sessions")
    if "ix_tracked_sessions_user_start" in existing:
        op.drop_index("ix_tracked_sessions_user_start", table_name="tracked_sessions")
