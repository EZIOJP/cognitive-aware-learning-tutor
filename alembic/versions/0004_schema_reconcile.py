"""Idempotent reconcile — legacy DBs, partial upgrades, additive columns.

Revision ID: 0004_reconcile
Revises: 0003_math_bank
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0004_reconcile"
down_revision: Union[str, None] = "0003_math_bank"
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
    # Legacy proto column (pre-Alembic create_all)
    if _has_table("users") and not _has_column("users", "password_plain"):
        with op.batch_alter_table("users") as batch:
            batch.add_column(sa.Column("password_plain", sa.String(255), nullable=True))

    if not _has_table("reading_definitions"):
        op.create_table(
            "reading_definitions",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("slug", sa.String(80), nullable=False),
            sa.Column("label", sa.String(160), nullable=False),
            sa.Column("unit", sa.String(40), nullable=True),
            sa.Column("source_type", sa.String(20), nullable=True),
            sa.Column("feature_id", sa.String(40), nullable=True),
            sa.Column("schema_json", sa.Text(), nullable=True),
            sa.Column("is_system", sa.Boolean(), default=True),
        )
        op.create_index("ix_reading_definitions_slug", "reading_definitions", ["slug"], unique=True)

    for table_sql in (
        (
            "sessions",
            [
                sa.Column("id", sa.Integer(), primary_key=True),
                sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE")),
                sa.Column("session_type", sa.String(40), nullable=False),
                sa.Column("started_at", sa.DateTime(), nullable=True),
                sa.Column("ended_at", sa.DateTime(), nullable=True),
                sa.Column("metadata_json", sa.Text(), nullable=True),
            ],
        ),
        (
            "readings",
            [
                sa.Column("id", sa.Integer(), primary_key=True),
                sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE")),
                sa.Column("definition_id", sa.Integer(), sa.ForeignKey("reading_definitions.id")),
                sa.Column("recorded_at", sa.DateTime(), nullable=True),
                sa.Column("value_numeric", sa.Float(), nullable=True),
                sa.Column("value_json", sa.Text(), nullable=True),
                sa.Column("session_id", sa.Integer(), sa.ForeignKey("sessions.id", ondelete="SET NULL"), nullable=True),
                sa.Column("source_device", sa.String(40), nullable=True),
                sa.Column("client_event_id", sa.String(64), nullable=True),
                sa.UniqueConstraint("user_id", "client_event_id", name="uq_reading_client_event"),
            ],
        ),
        (
            "daily_rollups",
            [
                sa.Column("id", sa.Integer(), primary_key=True),
                sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE")),
                sa.Column("date", sa.Date(), nullable=False),
                sa.Column("segments_json", sa.Text(), default="[]"),
                sa.Column("productive_minutes", sa.Integer(), default=0),
                sa.Column("sleep_minutes", sa.Integer(), default=0),
                sa.Column("vocab_events", sa.Integer(), default=0),
                sa.Column("math_attempts", sa.Integer(), default=0),
                sa.Column("stats_json", sa.Text(), default="{}"),
                sa.UniqueConstraint("user_id", "date", name="uq_rollup_user_date"),
            ],
        ),
        (
            "user_plugins",
            [
                sa.Column("id", sa.Integer(), primary_key=True),
                sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE")),
                sa.Column("plugin_id", sa.String(80), nullable=False),
                sa.Column("enabled", sa.Boolean(), default=True),
                sa.Column("config_json", sa.Text(), default="{}"),
                sa.UniqueConstraint("user_id", "plugin_id", name="uq_user_plugin"),
            ],
        ),
        (
            "life_daily_log",
            [
                sa.Column("id", sa.Integer(), primary_key=True),
                sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE")),
                sa.Column("date", sa.Date(), nullable=False),
                sa.Column("sleep_hours", sa.Float(), default=0),
                sa.Column("sleep_quality", sa.Integer(), default=3),
                sa.Column("exercise_minutes", sa.Integer(), default=0),
                sa.Column("water_glasses", sa.Integer(), default=0),
                sa.Column("meals_healthy", sa.Integer(), default=0),
                sa.Column("study_minutes", sa.Integer(), default=0),
                sa.Column("tasks_completed", sa.Integer(), default=0),
                sa.Column("deep_work_blocks", sa.Integer(), default=0),
                sa.Column("screen_time_hours", sa.Float(), default=0),
                sa.Column("social_media_minutes", sa.Integer(), default=0),
                sa.Column("outdoor_minutes", sa.Integer(), default=0),
                sa.Column("mood_score", sa.Integer(), default=3),
                sa.Column("stress_level", sa.Integer(), default=3),
                sa.Column("meditation_minutes", sa.Integer(), default=0),
                sa.Column("life_score", sa.Integer(), default=0),
                sa.Column("updated_at", sa.DateTime(), nullable=True),
                sa.UniqueConstraint("user_id", "date", name="uq_life_user_date"),
            ],
        ),
        (
            "quiz_sessions",
            [
                sa.Column("id", sa.Integer(), primary_key=True),
                sa.Column("external_id", sa.String(36), nullable=False),
                sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE")),
                sa.Column("quiz_type", sa.String(40), default="adaptive_group"),
                sa.Column("word_ids_json", sa.Text(), default="[]"),
                sa.Column("current_index", sa.Integer(), default=0),
                sa.Column("attempts_json", sa.Text(), default="[]"),
                sa.Column("started_at", sa.DateTime(), nullable=True),
                sa.Column("completed_at", sa.DateTime(), nullable=True),
            ],
        ),
    ):
        name, cols = table_sql
        if not _has_table(name):
            op.create_table(name, *cols)
            if name == "quiz_sessions":
                op.create_index("ix_quiz_sessions_external_id", name, ["external_id"], unique=True)
            if name == "readings":
                op.create_index("ix_readings_user_recorded", name, ["user_id", "recorded_at"])

    if not _has_table("math_questions"):
        op.create_table(
            "math_questions",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("external_id", sa.String(80), nullable=True),
            sa.Column("topic", sa.String(80), nullable=False),
            sa.Column("prompt", sa.String(1000), nullable=False),
            sa.Column("expected_answer", sa.String(500), nullable=False),
            sa.Column("explanation", sa.Text(), nullable=True),
            sa.Column("latex", sa.Text(), nullable=True),
            sa.Column("difficulty", sa.String(20), nullable=True),
            sa.Column("answer_format", sa.String(40), nullable=True),
            sa.Column("tags_json", sa.Text(), nullable=True),
            sa.Column("metadata_json", sa.Text(), nullable=True),
            sa.Column("source", sa.String(40), nullable=True),
            sa.Column("is_active", sa.Boolean(), default=True),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.UniqueConstraint("topic", "external_id", name="uq_math_question_topic_external"),
        )
        op.create_index("ix_math_questions_topic", "math_questions", ["topic"])

    if _has_table("math_attempts"):
        if not _has_column("math_attempts", "question_id"):
            with op.batch_alter_table("math_attempts") as batch:
                batch.add_column(sa.Column("question_id", sa.Integer(), nullable=True))
                batch.add_column(sa.Column("generated_id", sa.String(36), nullable=True))
        if _has_column("math_attempts", "template_id"):
            with op.batch_alter_table("math_attempts") as batch:
                batch.alter_column("template_id", existing_type=sa.Integer(), nullable=True)


def downgrade() -> None:
    # Reconcile revision is forward-safe only; no destructive downgrade.
    pass
