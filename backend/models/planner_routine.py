from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text

from backend.db.base import Base


class PlannerRoutine(Base):
    """Reusable daily blocks (bible, meals, bath) — applied to planner on demand."""

    __tablename__ = "planner_routines"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    title = Column(String, nullable=False)
    category = Column(String, nullable=False, default="personal")
    start_time = Column(String, nullable=False)  # HH:MM
    end_time = Column(String, nullable=True)
    duration_minutes = Column(Integer, nullable=True)
    days_json = Column(Text, nullable=False, default='["mon","tue","wed","thu","fri","sat","sun"]')
    color = Column(String, nullable=True)
    enabled = Column(Boolean, nullable=False, default=True)
    sort_order = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
