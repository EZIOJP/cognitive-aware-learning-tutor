"""Idempotent helpers for Alembic revisions (SQLite batch mode safe)."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


def inspector():
    return sa.inspect(op.get_bind())


def has_table(name: str) -> bool:
    return inspector().has_table(name)


def has_column(table: str, column: str) -> bool:
    if not has_table(table):
        return False
    return column in {c["name"] for c in inspector().get_columns(table)}


def create_table_if_missing(name: str, *columns, **table_kw) -> bool:
    if has_table(name):
        return False
    op.create_table(name, *columns, **table_kw)
    return True


def add_column_if_missing(table: str, column: sa.Column) -> bool:
    if not has_table(table) or has_column(table, column.name):
        return False
    with op.batch_alter_table(table) as batch:
        batch.add_column(column)
    return True


def create_index_if_missing(index_name: str, table: str, columns: list[str], *, unique: bool = False) -> bool:
    insp = inspector()
    if not has_table(table):
        return False
    existing = {idx["name"] for idx in insp.get_indexes(table)}
    if index_name in existing:
        return False
    op.create_index(index_name, table, columns, unique=unique)
    return True
