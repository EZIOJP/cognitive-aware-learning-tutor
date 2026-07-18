"""Per-user productivity policy — allowlist / denylist / app overrides."""

from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, Text, UniqueConstraint

from backend.db.base import Base


class ProductivityPolicy(Base):
    __tablename__ = "productivity_policies"
    __table_args__ = (UniqueConstraint("user_id", name="uq_productivity_policy_user"),)

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    # JSON: string[] of categories that count as productive
    productive_categories = Column(Text, nullable=False, default="[]")
    # JSON: string[] never productive unless session override
    blocked_categories = Column(Text, nullable=False, default="[]")
    # JSON: { key: category } exe/domain/title → forced category
    app_overrides = Column(Text, nullable=False, default="{}")
    threshold = Column(Integer, nullable=False, default=60)
    # Hard-block until daily productive goal (desktop tracker enforcement)
    hard_block_enabled = Column(Boolean, nullable=False, default=False)
    daily_goal_minutes = Column(Integer, nullable=False, default=240)
    hard_block_gaming = Column(Boolean, nullable=False, default=True)
    hard_block_exes = Column(Text, nullable=False, default="[]")
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
