"""Daily wearable snapshot from Amazfit / Zepp Mini Program."""

from datetime import UTC, date, datetime

from sqlalchemy import Date, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from backend.db.base import Base


class WearableDaily(Base):
    __tablename__ = "wearable_daily"
    __table_args__ = (UniqueConstraint("user_id", "local_date", name="uq_wearable_user_date"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    local_date: Mapped[date] = mapped_column(Date, index=True)
    source: Mapped[str] = mapped_column(String(40), default="mini_program")

    sleep_hours: Mapped[float | None] = mapped_column(Float, nullable=True)
    sleep_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sleep_deep_min: Mapped[int | None] = mapped_column(Integer, nullable=True)
    steps: Mapped[int | None] = mapped_column(Integer, nullable=True)
    step_target: Mapped[int | None] = mapped_column(Integer, nullable=True)
    calories: Mapped[int | None] = mapped_column(Integer, nullable=True)
    calorie_target: Mapped[int | None] = mapped_column(Integer, nullable=True)
    distance_m: Mapped[int | None] = mapped_column(Integer, nullable=True)
    hr_last: Mapped[int | None] = mapped_column(Integer, nullable=True)
    hr_resting: Mapped[int | None] = mapped_column(Integer, nullable=True)
    spo2: Mapped[int | None] = mapped_column(Integer, nullable=True)
    stress: Mapped[int | None] = mapped_column(Integer, nullable=True)
    pai_today: Mapped[float | None] = mapped_column(Float, nullable=True)
    pai_total: Mapped[float | None] = mapped_column(Float, nullable=True)
    stand_hours: Mapped[int | None] = mapped_column(Integer, nullable=True)
    stand_target: Mapped[int | None] = mapped_column(Integer, nullable=True)
    battery_pct: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Replay / dump identity (manual health dumper 4.0)
    last_captured_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_dump_id: Mapped[str | None] = mapped_column(String(80), nullable=True)
    last_chunk_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    last_checksum: Mapped[str | None] = mapped_column(String(40), nullable=True)

    payload_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    synced_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC)
    )


class WearableIngestEvent(Base):
    """Idempotency ledger for dump/chunk POSTs — duplicate event_id is a no-op."""

    __tablename__ = "wearable_ingest_event"
    __table_args__ = (
        UniqueConstraint("user_id", "event_id", name="uq_wearable_ingest_user_event"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    event_id: Mapped[str] = mapped_column(String(120), nullable=False)
    local_date: Mapped[date] = mapped_column(Date, index=True)
    dump_id: Mapped[str | None] = mapped_column(String(80), nullable=True)
    chunk_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    checksum: Mapped[str | None] = mapped_column(String(40), nullable=True)
    captured_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    accepted_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(UTC), nullable=False
    )
