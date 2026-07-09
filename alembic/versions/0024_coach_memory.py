"""Coach memory table — durable facts + per-day summaries."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0024_coach_memory"
down_revision: Union[str, None] = "0023_category_scores_readtime"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _insp():
    return sa.inspect(op.get_bind())


def upgrade() -> None:
    if _insp().has_table("coach_memories"):
        return
    op.create_table(
        "coach_memories",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("kind", sa.String(length=24), nullable=False),
        sa.Column("day", sa.String(length=10), nullable=True),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("user_id", "kind", "day", name="uq_coach_memory_user_kind_day"),
    )
    op.create_index("ix_coach_memories_user_id", "coach_memories", ["user_id"])
    op.create_index("ix_coach_memories_kind", "coach_memories", ["kind"])
    op.create_index("ix_coach_memories_day", "coach_memories", ["day"])


def downgrade() -> None:
    if _insp().has_table("coach_memories"):
        op.drop_table("coach_memories")
