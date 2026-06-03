from datetime import UTC, date, datetime

from sqlalchemy import Date, DateTime, Float, ForeignKey, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from backend.db.base import Base


class LifeDailyLog(Base):
    __tablename__ = "life_daily_log"
    __table_args__ = (UniqueConstraint("user_id", "date", name="uq_life_user_date"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    date: Mapped[date] = mapped_column(Date, index=True)

    sleep_hours: Mapped[float] = mapped_column(Float, default=0)
    sleep_quality: Mapped[int] = mapped_column(Integer, default=3)
    exercise_minutes: Mapped[int] = mapped_column(Integer, default=0)
    water_glasses: Mapped[int] = mapped_column(Integer, default=0)
    meals_healthy: Mapped[int] = mapped_column(Integer, default=0)

    study_minutes: Mapped[int] = mapped_column(Integer, default=0)
    tasks_completed: Mapped[int] = mapped_column(Integer, default=0)
    deep_work_blocks: Mapped[int] = mapped_column(Integer, default=0)

    screen_time_hours: Mapped[float] = mapped_column(Float, default=0)
    social_media_minutes: Mapped[int] = mapped_column(Integer, default=0)
    outdoor_minutes: Mapped[int] = mapped_column(Integer, default=0)

    mood_score: Mapped[int] = mapped_column(Integer, default=3)
    stress_level: Mapped[int] = mapped_column(Integer, default=3)
    meditation_minutes: Mapped[int] = mapped_column(Integer, default=0)

    life_score: Mapped[int] = mapped_column(Integer, default=0)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC)
    )
