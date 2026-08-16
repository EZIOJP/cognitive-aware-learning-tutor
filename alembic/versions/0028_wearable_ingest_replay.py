"""Add wearable ingest event ledger + replay metadata on wearable_daily."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0028_wearable_ingest_replay"
down_revision: Union[str, None] = "0027_wearable_daily"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _add_column_if_missing(table: str, column: sa.Column) -> None:
    insp = sa.inspect(op.get_bind())
    if not insp.has_table(table):
        return
    existing = {c["name"] for c in insp.get_columns(table)}
    if column.name in existing:
        return
    op.add_column(table, column)


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)

    _add_column_if_missing(
        "wearable_daily",
        sa.Column("last_captured_at", sa.DateTime(), nullable=True),
    )
    _add_column_if_missing(
        "wearable_daily",
        sa.Column("last_dump_id", sa.String(length=80), nullable=True),
    )
    _add_column_if_missing(
        "wearable_daily",
        sa.Column("last_chunk_id", sa.String(length=100), nullable=True),
    )
    _add_column_if_missing(
        "wearable_daily",
        sa.Column("last_checksum", sa.String(length=40), nullable=True),
    )

    if not insp.has_table("wearable_ingest_event"):
        op.create_table(
            "wearable_ingest_event",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column(
                "user_id",
                sa.Integer(),
                sa.ForeignKey("users.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("event_id", sa.String(length=120), nullable=False),
            sa.Column("local_date", sa.Date(), nullable=False),
            sa.Column("dump_id", sa.String(length=80), nullable=True),
            sa.Column("chunk_id", sa.String(length=100), nullable=True),
            sa.Column("checksum", sa.String(length=40), nullable=True),
            sa.Column("captured_at", sa.DateTime(), nullable=True),
            sa.Column("accepted_at", sa.DateTime(), nullable=False),
            sa.UniqueConstraint("user_id", "event_id", name="uq_wearable_ingest_user_event"),
        )
        op.create_index("ix_wearable_ingest_event_user_id", "wearable_ingest_event", ["user_id"])
        op.create_index(
            "ix_wearable_ingest_event_local_date", "wearable_ingest_event", ["local_date"]
        )


def downgrade() -> None:
    insp = sa.inspect(op.get_bind())
    if insp.has_table("wearable_ingest_event"):
        op.drop_table("wearable_ingest_event")
    for col in ("last_checksum", "last_chunk_id", "last_dump_id", "last_captured_at"):
        cols = {c["name"] for c in insp.get_columns("wearable_daily")} if insp.has_table(
            "wearable_daily"
        ) else set()
        if col in cols:
            op.drop_column("wearable_daily", col)
