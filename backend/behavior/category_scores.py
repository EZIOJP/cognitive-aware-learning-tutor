"""Read-time productivity scores from category_scores lookup table."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import Session

from backend.planner.service import iso_utc
from backend.models.category_score import CategoryScore

PRODUCTIVE_THRESHOLD = 60
DEFAULT_SCORE = 35


def build_scores_from_rules() -> dict[str, int]:
    """Unique (category, score) pairs from rule modules; highest score on conflict."""
    from backend.behavior.classification_service import ALLOWED_CATEGORIES
    from backend.behavior.domain_classify import _DOMAIN_RULES
    from backend.behavior.tracker_classify import _APP_RULES

    scores: dict[str, int] = {}

    def merge(category: str, score: int) -> None:
        if category not in scores or score > scores[category]:
            scores[category] = score

    for _, category, score in _APP_RULES:
        merge(category, score)
    for _, category, score in _DOMAIN_RULES:
        merge(category, score)

    merge("Study (Browser)", 78)
    merge("Entertainment", 15)
    merge("Other (Browser)", 35)

    for category in ALLOWED_CATEGORIES:
        if category not in scores:
            scores[category] = DEFAULT_SCORE

    return scores


def seed_category_scores(db: Session) -> None:
    """Populate category_scores from rule modules (migration helper + tests)."""
    now = datetime.now(UTC)
    for category, score in build_scores_from_rules().items():
        row = db.query(CategoryScore).filter(CategoryScore.category == category).first()
        if row is None:
            db.add(CategoryScore(category=category, score=score, updated_at=now))
        elif score > row.score:
            row.score = score
            row.updated_at = now
    db.commit()


def load_score_map(db: Session) -> dict[str, int]:
    """One SELECT per API handler — no module-level cache."""
    rows = db.query(CategoryScore.category, CategoryScore.score).all()
    return {category: score for category, score in rows}


def score_for_category(category: str | None, scores: dict[str, int]) -> int:
    if not category:
        return DEFAULT_SCORE
    return scores.get(category, DEFAULT_SCORE)


def serialize_tracked_session(
    row: Any,
    scores: dict[str, int],
    policy: dict | None = None,
) -> dict:
    """Shared payload shape for timeline / overlay / timetable responses."""
    from backend.behavior.productivity_policy import (
        resolve_category_with_overrides,
        resolve_session_score,
    )

    category = row.category if hasattr(row, "category") else row.get("category")
    app_name = row.app_name if hasattr(row, "app_name") else row.get("app_name")
    title = row.window_title if hasattr(row, "window_title") else row.get("window_title")
    override = None
    if hasattr(row, "override_productive"):
        override = row.override_productive
    elif isinstance(row, dict):
        override = row.get("override_productive")

    effective_cat = resolve_category_with_overrides(
        category, app_name=app_name, window_title=title, policy=policy
    )
    score = resolve_session_score(row, scores, policy) if policy is not None else score_for_category(category, scores)

    return {
        "session_id": row.session_id if hasattr(row, "session_id") else row.get("session_id"),
        "start_time": iso_utc(row.start_time) if hasattr(row, "start_time") else row.get("start_time"),
        "end_time": iso_utc(row.end_time) if hasattr(row, "end_time") else row.get("end_time"),
        "source": row.source if hasattr(row, "source") else row.get("source"),
        "category": effective_cat if policy is not None else category,
        "productivity_score": score,
        "window_title": title,
        "app_name": app_name,
        "task_id": row.task_id if hasattr(row, "task_id") else row.get("task_id"),
        "override_productive": override,
    }


# Backward-compat alias — older imports used serialize_session
serialize_session = serialize_tracked_session
