from datetime import UTC, date, datetime

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from backend.db.base import Base


class ReadingDefinition(Base):
    __tablename__ = "reading_definitions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    slug: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    label: Mapped[str] = mapped_column(String(160))
    unit: Mapped[str | None] = mapped_column(String(40), nullable=True)
    source_type: Mapped[str] = mapped_column(String(20), default="manual")
    feature_id: Mapped[str | None] = mapped_column(String(40), nullable=True)
    schema_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_system: Mapped[bool] = mapped_column(Boolean, default=True)


class ActivitySession(Base):
    __tablename__ = "sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    session_type: Mapped[str] = mapped_column(String(40), index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC))
    ended_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    metadata_json: Mapped[str | None] = mapped_column(Text, nullable=True)


class Reading(Base):
    __tablename__ = "readings"
    __table_args__ = (
        Index("ix_readings_user_recorded", "user_id", "recorded_at"),
        UniqueConstraint("user_id", "client_event_id", name="uq_reading_client_event"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    definition_id: Mapped[int] = mapped_column(
        ForeignKey("reading_definitions.id"), index=True
    )
    recorded_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC))
    value_numeric: Mapped[float | None] = mapped_column(Float, nullable=True)
    value_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    session_id: Mapped[int | None] = mapped_column(
        ForeignKey("sessions.id", ondelete="SET NULL"), nullable=True
    )
    source_device: Mapped[str | None] = mapped_column(String(40), nullable=True)
    client_event_id: Mapped[str | None] = mapped_column(String(64), nullable=True)


class DailyRollup(Base):
    __tablename__ = "daily_rollups"
    __table_args__ = (UniqueConstraint("user_id", "date", name="uq_rollup_user_date"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    date: Mapped[date] = mapped_column(Date, index=True)
    segments_json: Mapped[str] = mapped_column(Text, default="[]")
    productive_minutes: Mapped[int] = mapped_column(Integer, default=0)
    sleep_minutes: Mapped[int] = mapped_column(Integer, default=0)
    vocab_events: Mapped[int] = mapped_column(Integer, default=0)
    math_attempts: Mapped[int] = mapped_column(Integer, default=0)
    stats_json: Mapped[str] = mapped_column(Text, default="{}")


class UserPlugin(Base):
    __tablename__ = "user_plugins"
    __table_args__ = (UniqueConstraint("user_id", "plugin_id", name="uq_user_plugin"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    plugin_id: Mapped[str] = mapped_column(String(80))
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    config_json: Mapped[str] = mapped_column(Text, default="{}")
