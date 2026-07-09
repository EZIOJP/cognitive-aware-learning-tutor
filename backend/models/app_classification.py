"""On-demand LLM classification: suggestions (scratch) + cache (approved)."""

from sqlalchemy import Column, DateTime, Integer, String, Text, func

from backend.db.base import Base


class AppClassificationSuggestion(Base):
    __tablename__ = "app_classification_suggestions"

    id = Column(Integer, primary_key=True)
    key = Column(String, index=True, nullable=False)
    key_type = Column(String, nullable=False)
    suggested_category = Column(String, nullable=False)
    confidence = Column(Integer, default=0)
    sample_titles = Column(Text, nullable=True)
    occurrence_count = Column(Integer, default=1)
    status = Column(String, default="pending")
    reviewed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class AppClassificationCache(Base):
    __tablename__ = "app_classification_cache"

    id = Column(Integer, primary_key=True)
    key = Column(String, unique=True, index=True, nullable=False)
    key_type = Column(String, nullable=False)
    category = Column(String, nullable=False)
    source = Column(String, default="llm_reviewed")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
