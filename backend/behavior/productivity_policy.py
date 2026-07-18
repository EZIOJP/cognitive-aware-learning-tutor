"""Productivity policies — AI/ML deep-work defaults + score resolution."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import Session

from backend.behavior.category_scores import (
    DEFAULT_SCORE,
    PRODUCTIVE_THRESHOLD,
    load_score_map,
    score_for_category,
)
from backend.models.productivity_policy import ProductivityPolicy

# AI/ML / Scaler completion profile defaults
DEFAULT_PRODUCTIVE_CATEGORIES: list[str] = [
    "IDE / Code Editor",
    "Terminal",
    "Dev Tools",
    "Study / Reading",
    "Knowledge Work",
    "Office / Docs",
    "Design",
    "Coursework (Browser)",
    "Coding Practice",
    "Research",
    "Dev / Code",
    "Documentation",
    "Dev / Cloud",
    "AI Tools",
    "AI / ML",
    "Project Management",
]

DEFAULT_BLOCKED_CATEGORIES: list[str] = [
    "Gaming",
    "Video Streaming",
    "Live Streaming",
    "Music / Media",
    "Social Media",
    "Social / Forum",
    "Entertainment",
    "Shopping",
    "Browser",
    "Other (Browser)",
    "News",
    "Food Delivery",
]


def _loads_list(raw: str | None) -> list[str]:
    if not raw:
        return []
    try:
        data = json.loads(raw)
    except (TypeError, json.JSONDecodeError):
        return []
    if not isinstance(data, list):
        return []
    return [str(x).strip() for x in data if str(x).strip()]


def _loads_dict(raw: str | None) -> dict[str, str]:
    if not raw:
        return {}
    try:
        data = json.loads(raw)
    except (TypeError, json.JSONDecodeError):
        return {}
    if not isinstance(data, dict):
        return {}
    return {str(k).strip(): str(v).strip() for k, v in data.items() if str(k).strip() and str(v).strip()}


def default_policy_dict() -> dict[str, Any]:
    from backend.behavior.distraction_gate import DEFAULT_HARD_BLOCK_EXES

    return {
        "productive_categories": list(DEFAULT_PRODUCTIVE_CATEGORIES),
        "blocked_categories": list(DEFAULT_BLOCKED_CATEGORIES),
        "app_overrides": {},
        "threshold": PRODUCTIVE_THRESHOLD,
        "hard_block_enabled": False,
        "daily_goal_minutes": 240,
        "hard_block_gaming": True,
        "hard_block_exes": list(DEFAULT_HARD_BLOCK_EXES),
    }


def serialize_policy(row: ProductivityPolicy | None) -> dict[str, Any]:
    if row is None:
        return default_policy_dict()
    defaults = default_policy_dict()
    exes = _loads_list(getattr(row, "hard_block_exes", None))
    if not exes and not bool(getattr(row, "hard_block_enabled", False)):
        # Fresh row / empty JSON → seed defaults for UI
        exes = list(defaults["hard_block_exes"])
    return {
        "productive_categories": _loads_list(row.productive_categories),
        "blocked_categories": _loads_list(row.blocked_categories),
        "app_overrides": _loads_dict(row.app_overrides),
        "threshold": int(row.threshold or PRODUCTIVE_THRESHOLD),
        "hard_block_enabled": bool(getattr(row, "hard_block_enabled", False)),
        "daily_goal_minutes": int(getattr(row, "daily_goal_minutes", None) or 240),
        "hard_block_gaming": bool(getattr(row, "hard_block_gaming", True)),
        "hard_block_exes": exes,
    }


def get_or_create_policy(db: Session, user_id: int) -> ProductivityPolicy:
    row = (
        db.query(ProductivityPolicy)
        .filter(ProductivityPolicy.user_id == user_id)
        .first()
    )
    if row is not None:
        return row
    defaults = default_policy_dict()
    row = ProductivityPolicy(
        user_id=user_id,
        productive_categories=json.dumps(defaults["productive_categories"]),
        blocked_categories=json.dumps(defaults["blocked_categories"]),
        app_overrides=json.dumps(defaults["app_overrides"]),
        threshold=int(defaults["threshold"]),
        hard_block_enabled=bool(defaults["hard_block_enabled"]),
        daily_goal_minutes=int(defaults["daily_goal_minutes"]),
        hard_block_gaming=bool(defaults["hard_block_gaming"]),
        hard_block_exes=json.dumps(defaults["hard_block_exes"]),
        updated_at=datetime.now(UTC),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def update_policy(db: Session, user_id: int, body: dict[str, Any]) -> dict[str, Any]:
    row = get_or_create_policy(db, user_id)
    if "productive_categories" in body:
        cats = body["productive_categories"]
        if not isinstance(cats, list):
            raise ValueError("productive_categories must be a list")
        row.productive_categories = json.dumps([str(c).strip() for c in cats if str(c).strip()])
    if "blocked_categories" in body:
        cats = body["blocked_categories"]
        if not isinstance(cats, list):
            raise ValueError("blocked_categories must be a list")
        row.blocked_categories = json.dumps([str(c).strip() for c in cats if str(c).strip()])
    if "app_overrides" in body:
        ov = body["app_overrides"]
        if not isinstance(ov, dict):
            raise ValueError("app_overrides must be an object")
        cleaned = {
            str(k).strip(): str(v).strip()
            for k, v in ov.items()
            if str(k).strip() and str(v).strip()
        }
        row.app_overrides = json.dumps(cleaned)
        _sync_app_overrides_to_cache(db, cleaned)
    if "threshold" in body:
        thr = int(body["threshold"])
        if thr < 1 or thr > 100:
            raise ValueError("threshold must be 1–100")
        row.threshold = thr
    if "hard_block_enabled" in body:
        row.hard_block_enabled = bool(body["hard_block_enabled"])
    if "daily_goal_minutes" in body:
        mins = int(body["daily_goal_minutes"])
        if mins < 15 or mins > 16 * 60:
            raise ValueError("daily_goal_minutes must be 15–960")
        row.daily_goal_minutes = mins
    if "hard_block_gaming" in body:
        row.hard_block_gaming = bool(body["hard_block_gaming"])
    if "hard_block_exes" in body:
        exes = body["hard_block_exes"]
        if not isinstance(exes, list):
            raise ValueError("hard_block_exes must be a list")
        cleaned_exes: list[str] = []
        seen: set[str] = set()
        for item in exes:
            name = str(item).strip()
            if not name:
                continue
            key = name.lower()
            if key in seen:
                continue
            seen.add(key)
            cleaned_exes.append(name)
        row.hard_block_exes = json.dumps(cleaned_exes)
    row.updated_at = datetime.now(UTC)
    db.commit()
    db.refresh(row)
    return serialize_policy(row)


def _sync_app_overrides_to_cache(db: Session, overrides: dict[str, str]) -> None:
    """Write policy app overrides into classification cache so ingest always applies them."""
    from backend.models.app_classification import AppClassificationCache

    for key, category in overrides.items():
        key_type = "domain" if "." in key and " " not in key and not key.lower().endswith(".exe") else "exe"
        if " " in key or len(key) > 40:
            key_type = "title"
        row = db.query(AppClassificationCache).filter(AppClassificationCache.key == key).first()
        if row is None:
            db.add(
                AppClassificationCache(
                    key=key,
                    key_type=key_type,
                    category=category,
                    source="policy_override",
                )
            )
        else:
            row.category = category
            row.source = "policy_override"


def load_policy_dict(db: Session, user_id: int) -> dict[str, Any]:
    row = (
        db.query(ProductivityPolicy)
        .filter(ProductivityPolicy.user_id == user_id)
        .first()
    )
    if row is None:
        return default_policy_dict()
    return serialize_policy(row)


def resolve_category_with_overrides(
    category: str | None,
    *,
    app_name: str | None = None,
    window_title: str | None = None,
    policy: dict[str, Any] | None = None,
) -> str | None:
    """Apply policy app_overrides (exe / title key) before scoring."""
    if policy is None:
        return category
    overrides = policy.get("app_overrides") or {}
    if not isinstance(overrides, dict) or not overrides:
        return category
    exe = (app_name or "").strip()
    if exe and exe in overrides:
        return overrides[exe]
    exe_lower = exe.lower()
    for key, cat in overrides.items():
        if key.lower() == exe_lower or (exe_lower and (exe_lower.endswith(key.lower()) or key.lower() in exe_lower)):
            return cat
    title = (window_title or "").strip()
    if title and title in overrides:
        return overrides[title]
    # title prefix keys (first 80 chars like classification)
    if title:
        short = title[:80]
        if short in overrides:
            return overrides[short]
    return category


def resolve_productivity_score(
    category: str | None,
    scores: dict[str, int],
    policy: dict[str, Any] | None = None,
    *,
    override_productive: bool | None = None,
    app_name: str | None = None,
    window_title: str | None = None,
) -> int:
    """
    Single scoring path:
    - session override_productive True → max(threshold, category score)
    - session override_productive False → 0
    - blocked category → 0
    - productive allowlist → max(threshold, category score)
    - else → category_scores lookup
    """
    policy = policy or default_policy_dict()
    threshold = int(policy.get("threshold") or PRODUCTIVE_THRESHOLD)
    cat = resolve_category_with_overrides(
        category, app_name=app_name, window_title=window_title, policy=policy
    )

    if override_productive is True:
        base = score_for_category(cat, scores)
        return max(threshold, base if base else threshold)
    if override_productive is False:
        return 0

    blocked = set(policy.get("blocked_categories") or [])
    productive = set(policy.get("productive_categories") or [])

    if cat and cat in blocked:
        return 0

    base = score_for_category(cat, scores)
    if cat and cat in productive:
        return max(threshold, base)
    return base


def make_score_fn(
    scores: dict[str, int],
    policy: dict[str, Any] | None = None,
    *,
    session_overrides: dict[str, bool | None] | None = None,
    sessions_by_id: dict[str, Any] | None = None,
):
    """
    Return score_fn(category) compatible with effective_focus.
    When sessions_by_id provided, prefer looking up by matching category alone
    is insufficient — callers should use resolve_session_score instead for rows.
    """
    pol = policy or default_policy_dict()

    def _fn(category: str | None) -> int:
        return resolve_productivity_score(category, scores, pol)

    return _fn


def resolve_session_score(
    session: Any,
    scores: dict[str, int],
    policy: dict[str, Any] | None = None,
) -> int:
    override = None
    if hasattr(session, "override_productive"):
        override = session.override_productive
    elif isinstance(session, dict):
        override = session.get("override_productive")
    category = session.category if hasattr(session, "category") else session.get("category")
    app_name = session.app_name if hasattr(session, "app_name") else session.get("app_name")
    title = session.window_title if hasattr(session, "window_title") else session.get("window_title")
    return resolve_productivity_score(
        category,
        scores,
        policy,
        override_productive=override,
        app_name=app_name,
        window_title=title,
    )


def policy_aware_score_fn(db: Session, user_id: int):
    """Load scores + policy once; return (scores, policy, score_fn_for_category, threshold)."""
    scores = load_score_map(db)
    policy = load_policy_dict(db, user_id)
    threshold = int(policy.get("threshold") or PRODUCTIVE_THRESHOLD)

    def score_fn(category: str | None) -> int:
        return resolve_productivity_score(category, scores, policy)

    return scores, policy, score_fn, threshold
