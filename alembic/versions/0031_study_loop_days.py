"""Study Loop daily bite freeze (user_id + day)."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0031_study_loop_days"
down_revision: Union[str, None] = "0030_study_loop_sessions"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    insp = sa.inspect(op.get_bind())
    if insp.has_table("study_loop_days"):
        return
    op.create_table(
        "study_loop_days",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("day", sa.String(length=10), nullable=False),
        sa.Column("tags_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("mode", sa.String(length=8), nullable=False, server_default="B"),
        sa.Column("payload_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("user_id", "day", name="uq_study_loop_days_user_day"),
    )
    op.create_index("ix_study_loop_days_user_id", "study_loop_days", ["user_id"])
    op.create_index("ix_study_loop_days_day", "study_loop_days", ["day"])


def downgrade() -> None:
    insp = sa.inspect(op.get_bind())
    if not insp.has_table("study_loop_days"):
        return
    op.drop_table("study_loop_days")
