"""Productivity policy + session override columns."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0025_productivity_policy"
down_revision: Union[str, None] = "0024_coach_memory"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _insp():
    return sa.inspect(op.get_bind())


def upgrade() -> None:
    insp = _insp()
    if not insp.has_table("productivity_policies"):
        op.create_table(
            "productivity_policies",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("productive_categories", sa.Text(), nullable=False, server_default="[]"),
            sa.Column("blocked_categories", sa.Text(), nullable=False, server_default="[]"),
            sa.Column("app_overrides", sa.Text(), nullable=False, server_default="{}"),
            sa.Column("threshold", sa.Integer(), nullable=False, server_default="60"),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
            sa.UniqueConstraint("user_id", name="uq_productivity_policy_user"),
        )
        op.create_index("ix_productivity_policies_user_id", "productivity_policies", ["user_id"])

    cols = {c["name"] for c in insp.get_columns("tracked_sessions")} if insp.has_table("tracked_sessions") else set()
    if insp.has_table("tracked_sessions") and "override_productive" not in cols:
        op.add_column(
            "tracked_sessions",
            sa.Column("override_productive", sa.Boolean(), nullable=True),
        )


def downgrade() -> None:
    insp = _insp()
    if insp.has_table("tracked_sessions"):
        cols = {c["name"] for c in insp.get_columns("tracked_sessions")}
        if "override_productive" in cols:
            op.drop_column("tracked_sessions", "override_productive")
    if insp.has_table("productivity_policies"):
        op.drop_table("productivity_policies")
