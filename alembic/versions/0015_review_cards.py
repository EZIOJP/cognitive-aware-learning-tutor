"""Review cards and custom quiz decks for global spaced repetition."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0015_review_cards"
down_revision: Union[str, None] = "0014_knowledge_graph"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _insp():
    return sa.inspect(op.get_bind())


def _has_table(name: str) -> bool:
    return _insp().has_table(name)


def upgrade() -> None:
    if not _has_table("quiz_decks"):
        op.create_table(
            "quiz_decks",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("title", sa.String(200), server_default="My Quiz", nullable=False),
            sa.Column("topic", sa.String(160), nullable=True),
            sa.Column("domain", sa.String(24), server_default="study", nullable=False),
            sa.Column("items_json", sa.Text(), server_default="[]", nullable=False),
            sa.Column("time_limit_sec", sa.Integer(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.Column("updated_at", sa.DateTime(), nullable=True),
        )
        op.create_index("ix_quiz_decks_user_id", "quiz_decks", ["user_id"])

    if not _has_table("review_cards"):
        op.create_table(
            "review_cards",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("domain", sa.String(24), nullable=False),
            sa.Column("item_key", sa.String(200), nullable=False),
            sa.Column("label", sa.String(300), server_default="", nullable=False),
            sa.Column("topic", sa.String(160), nullable=True),
            sa.Column("note_path", sa.String(512), nullable=True),
            sa.Column("format", sa.String(20), server_default="mcq", nullable=False),
            sa.Column("payload_json", sa.Text(), server_default="{}", nullable=False),
            sa.Column("srs_json", sa.Text(), server_default="{}", nullable=False),
            sa.Column("deck_id", sa.Integer(), sa.ForeignKey("quiz_decks.id", ondelete="SET NULL"), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.Column("updated_at", sa.DateTime(), nullable=True),
            sa.UniqueConstraint("user_id", "item_key", name="uq_review_cards_user_item"),
        )
        op.create_index("ix_review_cards_user_id", "review_cards", ["user_id"])
        op.create_index("ix_review_cards_domain", "review_cards", ["domain"])
        op.create_index("ix_review_cards_item_key", "review_cards", ["item_key"])


def downgrade() -> None:
    if _has_table("review_cards"):
        op.drop_table("review_cards")
    if _has_table("quiz_decks"):
        op.drop_table("quiz_decks")
