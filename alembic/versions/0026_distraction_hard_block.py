"""Add hard-block-until-goal fields on productivity_policies."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0026_distraction_hard_block"
down_revision: Union[str, None] = "0025_productivity_policy"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _insp():
    return sa.inspect(op.get_bind())


def upgrade() -> None:
    insp = _insp()
    if not insp.has_table("productivity_policies"):
        return
    cols = {c["name"] for c in insp.get_columns("productivity_policies")}
    if "hard_block_enabled" not in cols:
        op.add_column(
            "productivity_policies",
            sa.Column("hard_block_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        )
    if "daily_goal_minutes" not in cols:
        op.add_column(
            "productivity_policies",
            sa.Column("daily_goal_minutes", sa.Integer(), nullable=False, server_default="240"),
        )
    if "hard_block_gaming" not in cols:
        op.add_column(
            "productivity_policies",
            sa.Column("hard_block_gaming", sa.Boolean(), nullable=False, server_default=sa.true()),
        )
    if "hard_block_exes" not in cols:
        op.add_column(
            "productivity_policies",
            sa.Column("hard_block_exes", sa.Text(), nullable=False, server_default="[]"),
        )


def downgrade() -> None:
    insp = _insp()
    if not insp.has_table("productivity_policies"):
        return
    cols = {c["name"] for c in insp.get_columns("productivity_policies")}
    for name in ("hard_block_exes", "hard_block_gaming", "daily_goal_minutes", "hard_block_enabled"):
        if name in cols:
            op.drop_column("productivity_policies", name)
