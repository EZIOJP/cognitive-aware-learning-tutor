"""Add wearable_daily table for full Amazfit / Zepp snapshots."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0027_wearable_daily"
down_revision: Union[str, None] = "0026_distraction_hard_block"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    insp = sa.inspect(op.get_bind())
    if insp.has_table("wearable_daily"):
        return
    op.create_table(
        "wearable_daily",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("local_date", sa.Date(), nullable=False),
        sa.Column("source", sa.String(length=40), nullable=False, server_default="mini_program"),
        sa.Column("sleep_hours", sa.Float(), nullable=True),
        sa.Column("sleep_score", sa.Integer(), nullable=True),
        sa.Column("sleep_deep_min", sa.Integer(), nullable=True),
        sa.Column("steps", sa.Integer(), nullable=True),
        sa.Column("step_target", sa.Integer(), nullable=True),
        sa.Column("calories", sa.Integer(), nullable=True),
        sa.Column("calorie_target", sa.Integer(), nullable=True),
        sa.Column("distance_m", sa.Integer(), nullable=True),
        sa.Column("hr_last", sa.Integer(), nullable=True),
        sa.Column("hr_resting", sa.Integer(), nullable=True),
        sa.Column("spo2", sa.Integer(), nullable=True),
        sa.Column("stress", sa.Integer(), nullable=True),
        sa.Column("pai_today", sa.Float(), nullable=True),
        sa.Column("pai_total", sa.Float(), nullable=True),
        sa.Column("stand_hours", sa.Integer(), nullable=True),
        sa.Column("stand_target", sa.Integer(), nullable=True),
        sa.Column("battery_pct", sa.Integer(), nullable=True),
        sa.Column("payload_json", sa.Text(), nullable=True),
        sa.Column("synced_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("user_id", "local_date", name="uq_wearable_user_date"),
    )
    op.create_index("ix_wearable_daily_user_id", "wearable_daily", ["user_id"])
    op.create_index("ix_wearable_daily_local_date", "wearable_daily", ["local_date"])


def downgrade() -> None:
    insp = sa.inspect(op.get_bind())
    if insp.has_table("wearable_daily"):
        op.drop_table("wearable_daily")
