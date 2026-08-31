"""Add users.display_name for the local owner profile."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0029_user_display_name"
down_revision: Union[str, None] = "0028_wearable_ingest_replay"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if not insp.has_table("users"):
        return
    existing = {c["name"] for c in insp.get_columns("users")}
    if "display_name" in existing:
        return
    op.add_column("users", sa.Column("display_name", sa.String(length=80), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if not insp.has_table("users"):
        return
    existing = {c["name"] for c in insp.get_columns("users")}
    if "display_name" not in existing:
        return
    op.drop_column("users", "display_name")
