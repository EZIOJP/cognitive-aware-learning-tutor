from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Integer, String

from backend.db.base import Base


class CategoryScore(Base):
    __tablename__ = "category_scores"

    category = Column(String, primary_key=True)
    score = Column(Integer, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
