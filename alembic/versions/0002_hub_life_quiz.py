"""Hub, life log, quiz sessions, reading definitions.

Revision ID: 0002_hub
Revises: 0001_baseline
Create Date: 2026-06-02

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0002_hub"
down_revision: Union[str, None] = "0001_baseline"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
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

    op.create_table(
        "sessions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE")),
        sa.Column("session_type", sa.String(40), nullable=False),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("ended_at", sa.DateTime(), nullable=True),
        sa.Column("metadata_json", sa.Text(), nullable=True),
    )

    op.create_table(
        "readings",
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
    )
    op.create_index("ix_readings_user_recorded", "readings", ["user_id", "recorded_at"])

    op.create_table(
        "daily_rollups",
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
    )

    op.create_table(
        "user_plugins",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE")),
        sa.Column("plugin_id", sa.String(80), nullable=False),
        sa.Column("enabled", sa.Boolean(), default=True),
        sa.Column("config_json", sa.Text(), default="{}"),
        sa.UniqueConstraint("user_id", "plugin_id", name="uq_user_plugin"),
    )

    op.create_table(
        "life_daily_log",
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
    )

    op.create_table(
        "quiz_sessions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("external_id", sa.String(36), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE")),
        sa.Column("quiz_type", sa.String(40), default="adaptive_group"),
        sa.Column("word_ids_json", sa.Text(), default="[]"),
        sa.Column("current_index", sa.Integer(), default=0),
        sa.Column("attempts_json", sa.Text(), default="[]"),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_quiz_sessions_external_id", "quiz_sessions", ["external_id"], unique=True)


def downgrade() -> None:
    op.drop_table("quiz_sessions")
    op.drop_table("life_daily_log")
    op.drop_table("user_plugins")
    op.drop_table("daily_rollups")
    op.drop_table("readings")
    op.drop_table("sessions")
    op.drop_table("reading_definitions")
