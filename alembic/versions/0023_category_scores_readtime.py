"""Read-time category_scores table + tracked_sessions_scored view; drop stored score."""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0023_category_scores_readtime"
down_revision: Union[str, None] = "0022_app_classification"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _insp():
    return sa.inspect(op.get_bind())


def _seed_category_scores() -> None:
    from datetime import UTC, datetime

    from backend.behavior.category_scores import build_scores_from_rules

    conn = op.get_bind()
    now = datetime.now(UTC)
    for category, score in build_scores_from_rules().items():
        conn.execute(
            sa.text(
                "INSERT INTO category_scores (category, score, updated_at) "
                "VALUES (:category, :score, :updated_at) "
                "ON CONFLICT(category) DO UPDATE SET "
                "score = MAX(category_scores.score, excluded.score), "
                "updated_at = excluded.updated_at"
            ),
            {"category": category, "score": score, "updated_at": now},
        )


def upgrade() -> None:
    if not _insp().has_table("category_scores"):
        op.create_table(
            "category_scores",
            sa.Column("category", sa.String(), nullable=False),
            sa.Column("score", sa.Integer(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
            sa.PrimaryKeyConstraint("category"),
        )
        _seed_category_scores()

    if _insp().has_table("tracked_sessions"):
        cols = {c["name"] for c in _insp().get_columns("tracked_sessions")}
        if "productivity_score" in cols:
            with op.batch_alter_table("tracked_sessions") as batch_op:
                batch_op.drop_column("productivity_score")

    op.execute(sa.text("DROP VIEW IF EXISTS tracked_sessions_scored"))
    op.execute(
        sa.text(
            """
            CREATE VIEW tracked_sessions_scored AS
            SELECT ts.*, COALESCE(cs.score, 35) AS productivity_score
            FROM tracked_sessions ts
            LEFT JOIN category_scores cs ON cs.category = ts.category
            """
        )
    )


def downgrade() -> None:
    if _insp().has_table("tracked_sessions"):
        cols = {c["name"] for c in _insp().get_columns("tracked_sessions")}
        if "productivity_score" not in cols:
            with op.batch_alter_table("tracked_sessions") as batch_op:
                batch_op.add_column(sa.Column("productivity_score", sa.Integer(), nullable=True))

            op.execute(
                sa.text(
                    """
                    UPDATE tracked_sessions
                    SET productivity_score = (
                        SELECT productivity_score
                        FROM tracked_sessions_scored
                        WHERE tracked_sessions_scored.session_id = tracked_sessions.session_id
                    )
                    """
                )
            )

    op.execute(sa.text("DROP VIEW IF EXISTS tracked_sessions_scored"))

    if _insp().has_table("category_scores"):
        op.drop_table("category_scores")
