"""Add schedule_json to timetables for weekly grid import.

Revision ID: 0016_timetable_schedule
Revises: 13fcaceaf751
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0016_timetable_schedule"
down_revision: Union[str, None] = "13fcaceaf751"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _insp():
    return sa.inspect(op.get_bind())


def _has_column(table: str, col: str) -> bool:
    if not _insp().has_table(table):
        return False
    return col in {c["name"] for c in _insp().get_columns(table)}


def upgrade() -> None:
    if not _has_column("timetables", "schedule_json"):
        with op.batch_alter_table("timetables", schema=None) as batch_op:
            batch_op.add_column(sa.Column("schedule_json", sa.Text(), nullable=True))


def downgrade() -> None:
    if _has_column("timetables", "schedule_json"):
        with op.batch_alter_table("timetables", schema=None) as batch_op:
            batch_op.drop_column("schedule_json")
