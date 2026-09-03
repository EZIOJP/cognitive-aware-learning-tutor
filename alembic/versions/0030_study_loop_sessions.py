"""Study Loop session table (read gate → practice)."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0030_study_loop_sessions"
down_revision: Union[str, None] = "0029_user_display_name"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    insp = sa.inspect(op.get_bind())
    if insp.has_table("study_loop_sessions"):
        return
    op.create_table(
        "study_loop_sessions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("session_id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("tag", sa.String(length=160), nullable=False),
        sa.Column("read_completed", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("read_card_ids_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("practice_quiz_session_id", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("session_id", name="uq_study_loop_sessions_session_id"),
    )
    op.create_index("ix_study_loop_sessions_session_id", "study_loop_sessions", ["session_id"])
    op.create_index("ix_study_loop_sessions_user_id", "study_loop_sessions", ["user_id"])
    op.create_index("ix_study_loop_sessions_tag", "study_loop_sessions", ["tag"])


def downgrade() -> None:
    insp = sa.inspect(op.get_bind())
    if not insp.has_table("study_loop_sessions"):
        return
    op.drop_table("study_loop_sessions")
