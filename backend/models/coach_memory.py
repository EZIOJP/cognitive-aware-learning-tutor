"""Persistent coach memory — durable facts + one compact summary line per day."""

from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint

from backend.db.base import Base


class CoachMemory(Base):
    """Bounded long-term memory for the AI coach.

    kind="fact": durable items extracted from chat (goals, deadlines, preferences, struggles).
    kind="day_summary": one row per day condensing that day's hub data; day column set.
    """

    __tablename__ = "coach_memories"
    __table_args__ = (
        UniqueConstraint("user_id", "kind", "day", name="uq_coach_memory_user_kind_day"),
    )

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    kind = Column(String(24), nullable=False, index=True)  # fact | day_summary
    day = Column(String(10), nullable=True, index=True)  # YYYY-MM-DD, only for day_summary
    content = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
