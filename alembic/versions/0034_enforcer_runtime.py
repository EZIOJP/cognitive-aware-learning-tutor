"""enforcer_runtime: shared kill policy snapshot for native C++ enforcer."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0034_enforcer_runtime"
down_revision: Union[str, None] = "0033_break_reward"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if not insp.has_table("enforcer_runtime"):
        op.create_table(
            "enforcer_runtime",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column(
                "user_id",
                sa.Integer(),
                sa.ForeignKey("users.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("hard_block_armed", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("gate_locked", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("incubation_active", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("exes_json", sa.Text(), nullable=False, server_default="[]"),
            sa.Column("note", sa.String(length=240), nullable=False, server_default=""),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        )

    insp = sa.inspect(bind)
    indexes = {ix["name"] for ix in insp.get_indexes("enforcer_runtime")}
    if "ix_enforcer_runtime_user_id" not in indexes:
        op.create_index(
            "ix_enforcer_runtime_user_id",
            "enforcer_runtime",
            ["user_id"],
            unique=True,
        )


def downgrade() -> None:
    insp = sa.inspect(op.get_bind())
    if not insp.has_table("enforcer_runtime"):
        return
    indexes = {ix["name"] for ix in insp.get_indexes("enforcer_runtime")}
    if "ix_enforcer_runtime_user_id" in indexes:
        op.drop_index("ix_enforcer_runtime_user_id", table_name="enforcer_runtime")
    op.drop_table("enforcer_runtime")
