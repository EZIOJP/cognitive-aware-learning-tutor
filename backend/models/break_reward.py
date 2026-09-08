"""Incubation break sessions + earned free-time ledger (Desktop Tracker v2c)."""

from datetime import UTC, datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.db.base import Base


class BreakSession(Base):
    """Timed break window — incubation (mandatory) or earned free spend."""

    __tablename__ = "break_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    started_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(UTC), nullable=False, index=True
    )
    duration_sec: Mapped[int] = mapped_column(Integer, nullable=False)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    source_session_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    payload_json: Mapped[str] = mapped_column(Text, default="{}", nullable=False)


class RewardLedger(Base):
    """Running earned free-time ledger (+earn / −spend minutes)."""

    __tablename__ = "reward_ledger"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    delta_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    reason: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(UTC), nullable=False, index=True
    )
    ref_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    balance_after: Mapped[int] = mapped_column(Integer, nullable=False)
