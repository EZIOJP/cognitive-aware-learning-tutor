"""User-defined features and per-user metric definitions.

Revision ID: 0006_user_features
Revises: 0005_words_hub
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0006_user_features"
down_revision: Union[str, None] = "0005_words_hub"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _insp():
    return sa.inspect(op.get_bind())


def _has_table(name: str) -> bool:
    return _insp().has_table(name)


def _has_column(table: str, col: str) -> bool:
    if not _has_table(table):
        return False
    return col in {c["name"] for c in _insp().get_columns(table)}


def upgrade() -> None:
    if not _has_column("reading_definitions", "user_id"):
        with op.batch_alter_table("reading_definitions") as batch:
            batch.add_column(sa.Column("user_id", sa.Integer(), nullable=True))
            batch.create_foreign_key(
                "fk_reading_definitions_user_id",
                "users",
                ["user_id"],
                ["id"],
                ondelete="CASCADE",
            )

    if not _has_table("user_features"):
        op.create_table(
            "user_features",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("feature_id", sa.String(80), nullable=False),
            sa.Column("name", sa.String(160), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("enabled", sa.Boolean(), server_default=sa.text("1"), nullable=False),
            sa.Column("config_json", sa.Text(), server_default="{}", nullable=False),
            sa.Column(
                "created_at",
                sa.DateTime(),
                server_default=sa.text("(CURRENT_TIMESTAMP)"),
                nullable=False,
            ),
            sa.UniqueConstraint("user_id", "feature_id", name="uq_user_feature"),
        )
        op.create_index("ix_user_features_user_id", "user_features", ["user_id"])


def downgrade() -> None:
    if _has_table("user_features"):
        op.drop_table("user_features")
    if _has_column("reading_definitions", "user_id"):
        with op.batch_alter_table("reading_definitions") as batch:
            batch.drop_constraint("fk_reading_definitions_user_id", type_="foreignkey")
            batch.drop_column("user_id")
