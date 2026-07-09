from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from backend.db.base import Base


class PlannerBlock(Base):
    __tablename__ = "planner_blocks"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    title = Column(String, nullable=False)
    category = Column(String, nullable=False, default="study")
    start_at = Column(DateTime(timezone=True), nullable=False, index=True)
    end_at = Column(DateTime(timezone=True), nullable=False)
    planned_minutes = Column(Integer, nullable=False)
    remaining_minutes = Column(Integer, nullable=False)
    status = Column(String, nullable=False, default="scheduled")
    rolled_from_id = Column(Integer, ForeignKey("planner_blocks.id", ondelete="SET NULL"), nullable=True)
    roll_count = Column(Integer, nullable=False, default=0)
    task_id = Column(Integer, ForeignKey("timetable_tasks.id", ondelete="SET NULL"), nullable=True)
    color = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    rolled_from = relationship("PlannerBlock", remote_side=[id], foreign_keys=[rolled_from_id])
