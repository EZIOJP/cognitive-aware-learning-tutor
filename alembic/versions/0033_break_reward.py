"""Incubation break_sessions + reward_ledger (Desktop Tracker v2c)."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0033_break_reward"
down_revision: Union[str, None] = "0032_tracked_session_day_indexes"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    insp = sa.inspect(op.get_bind())
    if not insp.has_table("break_sessions"):
        op.create_table(
            "break_sessions",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column(
                "user_id",
                sa.Integer(),
                sa.ForeignKey("users.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("kind", sa.String(length=32), nullable=False),
            sa.Column("started_at", sa.DateTime(), nullable=False),
            sa.Column("duration_sec", sa.Integer(), nullable=False),
            sa.Column("ended_at", sa.DateTime(), nullable=True),
            sa.Column("source_session_id", sa.String(length=120), nullable=True),
            sa.Column("payload_json", sa.Text(), nullable=False, server_default="{}"),
        )
        op.create_index("ix_break_sessions_user_id", "break_sessions", ["user_id"])
        op.create_index("ix_break_sessions_kind", "break_sessions", ["kind"])
        op.create_index("ix_break_sessions_started_at", "break_sessions", ["started_at"])

    if not insp.has_table("reward_ledger"):
        op.create_table(
            "reward_ledger",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column(
                "user_id",
                sa.Integer(),
                sa.ForeignKey("users.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("delta_minutes", sa.Integer(), nullable=False),
            sa.Column("reason", sa.String(length=64), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("ref_id", sa.String(length=120), nullable=True),
            sa.Column("balance_after", sa.Integer(), nullable=False),
        )
        op.create_index("ix_reward_ledger_user_id", "reward_ledger", ["user_id"])
        op.create_index("ix_reward_ledger_reason", "reward_ledger", ["reason"])
        op.create_index("ix_reward_ledger_created_at", "reward_ledger", ["created_at"])


def downgrade() -> None:
    insp = sa.inspect(op.get_bind())
    if insp.has_table("reward_ledger"):
        op.drop_table("reward_ledger")
    if insp.has_table("break_sessions"):
        op.drop_table("break_sessions")
