from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from backend.db.base import Base


class Timetable(Base):
    __tablename__ = "timetables"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    name = Column(String, nullable=False)
    schedule_json = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    tasks = relationship("TimetableTask", back_populates="timetable", cascade="all, delete-orphan")


class TimetableTask(Base):
    __tablename__ = "timetable_tasks"

    id = Column(Integer, primary_key=True, index=True)
    timetable_id = Column(Integer, ForeignKey("timetables.id", ondelete="CASCADE"), nullable=False)
    title = Column(String, nullable=False)
    description = Column(String, nullable=True)

    timetable = relationship("Timetable", back_populates="tasks")
    sessions = relationship("TrackedSession", back_populates="task", cascade="all, delete-orphan")


class TrackedSession(Base):
    __tablename__ = "tracked_sessions"

    session_id = Column(String, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    task_id = Column(Integer, ForeignKey("timetable_tasks.id", ondelete="SET NULL"), nullable=True)
    
    start_time = Column(DateTime(timezone=True), nullable=False)
    end_time = Column(DateTime(timezone=True), nullable=False)
    
    source = Column(String, nullable=False, default="manual")
    category = Column(String, nullable=True)
    window_title = Column(String(512), nullable=True)
    app_name = Column(String(255), nullable=True)
    category_source = Column(String, nullable=True, default="rule")
    category_before_llm = Column(String, nullable=True)

    task = relationship("TimetableTask", back_populates="sessions")
