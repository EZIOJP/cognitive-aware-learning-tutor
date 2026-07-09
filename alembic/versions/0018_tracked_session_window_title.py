"""Add window_title to tracked_sessions for desktop tracker."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0018_tracked_session_window_title"
down_revision: Union[str, None] = "0017_planner_blocks"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _insp():
    return sa.inspect(op.get_bind())


def upgrade() -> None:
    if not _insp().has_table("tracked_sessions"):
        return
    cols = {c["name"] for c in _insp().get_columns("tracked_sessions")}
    if "window_title" not in cols:
        with op.batch_alter_table("tracked_sessions", schema=None) as batch_op:
            batch_op.add_column(sa.Column("window_title", sa.String(length=512), nullable=True))
    if "app_name" not in cols:
        with op.batch_alter_table("tracked_sessions", schema=None) as batch_op:
            batch_op.add_column(sa.Column("app_name", sa.String(length=255), nullable=True))


def downgrade() -> None:
    if not _insp().has_table("tracked_sessions"):
        return
    cols = {c["name"] for c in _insp().get_columns("tracked_sessions")}
    if "window_title" in cols:
        with op.batch_alter_table("tracked_sessions", schema=None) as batch_op:
            batch_op.drop_column("window_title")
    cols = {c["name"] for c in _insp().get_columns("tracked_sessions")}
    if "app_name" in cols:
        with op.batch_alter_table("tracked_sessions", schema=None) as batch_op:
            batch_op.drop_column("app_name")
