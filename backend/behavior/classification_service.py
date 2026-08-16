"""On-demand LLM classification for uncategorized tracker events.

Pure service functions — no router or FastAPI dependencies.
"""

from __future__ import annotations

import json
import logging
import re
from datetime import UTC, datetime

from sqlalchemy import func, update
from sqlalchemy.orm import Session

from backend.core.ollama_client import ollama_generate
from backend.models.app_classification import (
    AppClassificationCache,
    AppClassificationSuggestion,
)
from backend.models.timetable import TrackedSession

log = logging.getLogger("classification")

ALLOWED_CATEGORIES = {
    "IDE / Code Editor",
    "Terminal",
    "Dev Tools",
    "Study / Reading",
    "Knowledge Work",
    "Office / Docs",
    "Design",
    "Communication",
    "Browser",
    "Coursework (Browser)",
    "Coding Practice",
    "Research",
    "Dev / Code",
    "Documentation",
    "Dev / Cloud",
    "AI Tools",
    "AI / ML",
    "Tech Reading",
    "Reference",
    "Project Management",
    "Social Media",
    "Social / Forum",
    "Professional Social",
    "Video (YouTube)",
    "Video Streaming",
    "Live Streaming",
    "Shopping",
    "News",
    "Finance",
    "Entertainment",
    "Study (Browser)",
    "Other (Browser)",
    "File Manager",
    "Music / Media",
    "Gaming",
    "System Tools",
    "Other",
    "Spiritual",
}

_SYSTEM_PROMPT = (
    "Classify this application or website into EXACTLY ONE category "
    "from this fixed list: {categories}\n\n"
    'Respond with ONLY this JSON object, nothing else — no markdown fences, '
    "no explanation, no preamble:\n"
    '{{"category": "<one from the list>", "confidence": <integer 0-95>}}'
).format(categories=", ".join(sorted(ALLOWED_CATEGORIES)))

_GENERIC_DOMAIN_CATEGORIES = frozenset({"Browser", "Other (Browser)", "Other"})
_BROWSER_CATS = ("Browser", "Other (Browser)")

_TITLE_BROWSER_SUFFIX = re.compile(
    r"\s*[-–—]\s*(Microsoft\s*Edge|Google\s*Chrome|Mozilla\s*Firefox|Brave|Opera|Arc|Safari)\s*$",
    re.I,
)


def normalize_title_key(title: str) -> str:
    """Strip browser suffix from window title — same key as find_uncategorized_keys."""
    if not title:
        return ""
    return _TITLE_BROWSER_SUFFIX.sub("", title).strip()[:80]


def classify_key_via_rules(
    key: str,
    key_type: str,
    sample_titles: list[str],
) -> tuple[str, int] | None:
    """Regex/domain rules before LLM — returns None if still generic."""
    if key_type != "domain":
        return None
    from backend.behavior.domain_classify import classify_browser_title, classify_domain

    title = sample_titles[0] if sample_titles else key
    for cat, conf in (classify_domain(key, title), classify_browser_title(title)):
        if cat in ALLOWED_CATEGORIES and cat not in _GENERIC_DOMAIN_CATEGORIES:
            return cat, conf
    return None


def parse_llm_category(raw: str) -> tuple[str, int]:
    cleaned = re.sub(r"```json|```", "", raw).strip()
    match = re.search(r"\{.*?\}", cleaned, re.DOTALL)
    if not match:
        return "Other", 0
    try:
        data = json.loads(match.group(0))
    except json.JSONDecodeError:
        return "Other", 0
    category = str(data.get("category", "")).strip()
    try:
        confidence = max(0, min(95, int(data.get("confidence", 0))))
    except (TypeError, ValueError):
        confidence = 0
    if category not in ALLOWED_CATEGORIES:
        return "Other", 0
    return category, confidence


def classify_key_via_llm(
    key: str,
    key_type: str,
    sample_titles: list[str],
    *,
    llm_tier: str | None = None,
) -> tuple[str, int] | None:
    context_label = "application executable" if key_type == "exe" else "website domain"
    titles_text = "\n".join(f"  - {t}" for t in sample_titles[:3]) if sample_titles else "(no titles)"
    prompt = (
        f"The {context_label} is: {key}\n"
        f"Sample window/page titles:\n{titles_text}\n\n"
        "Classify it now."
    )
    raw = ollama_generate(prompt, system_prompt=_SYSTEM_PROMPT, timeout=30.0, task="classify", tier=llm_tier)
    if not raw:
        return None
    category, confidence = parse_llm_category(raw)
    if category == "Other" and confidence == 0:
        return None
    return category, confidence


def find_uncategorized_keys(
    db: Session,
    *,
    limit: int = 20,
    include_browser: bool = True,
) -> list[dict]:
    cached_keys = {
        row.key
        for row in db.query(AppClassificationCache.key).all()
    }

    results: list[dict] = []

    # Desktop apps classified as "Other"
    app_rows = (
        db.query(
            TrackedSession.app_name,
            func.count().label("cnt"),
        )
        .filter(
            TrackedSession.category == "Other",
            TrackedSession.app_name.isnot(None),
            TrackedSession.app_name != "",
        )
        .group_by(TrackedSession.app_name)
        .order_by(func.count().desc())
        .limit(limit + len(cached_keys))
        .all()
    )

    for app_name, cnt in app_rows:
        if not app_name or app_name.strip() in cached_keys:
            continue
        titles = [
            row.window_title
            for row in db.query(TrackedSession.window_title)
            .filter(
                TrackedSession.app_name == app_name,
                TrackedSession.window_title.isnot(None),
                TrackedSession.window_title != "",
            )
            .limit(3)
            .all()
            if row.window_title
        ]
        results.append({
            "key": app_name.strip(),
            "key_type": "exe",
            "occurrence_count": cnt,
            "sample_titles": titles,
        })
        if len(results) >= limit:
            break

    if not include_browser:
        return results

    # Browser sessions classified as generic "Browser" or "Other (Browser)"
    browser_cats = ("Browser", "Other (Browser)")
    browser_rows = (
        db.query(
            TrackedSession.window_title,
            func.count().label("cnt"),
        )
        .filter(
            TrackedSession.category.in_(browser_cats),
            TrackedSession.window_title.isnot(None),
            TrackedSession.window_title != "",
            (TrackedSession.category_source.is_(None)) | (TrackedSession.category_source == "rule"),
        )
        .group_by(TrackedSession.window_title)
        .order_by(func.count().desc())
        .limit(limit)
        .all()
    )

    for title, cnt in browser_rows:
        if not title or title.strip() in cached_keys:
            continue
        short_key = normalize_title_key(title)
        if short_key in cached_keys:
            continue
        results.append({
            "key": short_key,
            "key_type": "domain",
            "occurrence_count": cnt,
            "sample_titles": [title],
        })
        if len(results) >= limit * 2:
            break

    return results


def _domain_session_rows(db: Session, key: str) -> list[TrackedSession]:
    rows = (
        db.query(TrackedSession)
        .filter(
            TrackedSession.category.in_(_BROWSER_CATS),
            TrackedSession.window_title.isnot(None),
            TrackedSession.window_title != "",
            (TrackedSession.category_source.is_(None)) | (TrackedSession.category_source == "rule"),
        )
        .all()
    )
    return [r for r in rows if normalize_title_key(r.window_title or "") == key]


def _domain_revert_rows(db: Session, key: str) -> list[TrackedSession]:
    rows = (
        db.query(TrackedSession)
        .filter(
            TrackedSession.category_source == "llm_reviewed",
            TrackedSession.window_title.isnot(None),
            TrackedSession.window_title != "",
        )
        .all()
    )
    return [r for r in rows if normalize_title_key(r.window_title or "") == key]


def backfill_approved(
    db: Session,
    key: str,
    key_type: str,
    new_category: str,
) -> int:
    if key_type == "domain":
        rows = _domain_session_rows(db, key)
        for row in rows:
            row.category_before_llm = row.category
            row.category = new_category
            row.category_source = "llm_reviewed"
        db.flush()
        return len(rows)

    result = db.execute(
        update(TrackedSession)
        .where(
            TrackedSession.app_name == key,
            TrackedSession.category == "Other",
            (TrackedSession.category_source.is_(None)) | (TrackedSession.category_source == "rule"),
        )
        .values(
            category=new_category,
            category_source="llm_reviewed",
            category_before_llm="Other",
        )
    )
    return result.rowcount  # type: ignore[union-attr]


def revert_backfill(db: Session, key: str, key_type: str = "exe") -> int:
    if key_type == "domain":
        rows = _domain_revert_rows(db, key)
        for row in rows:
            row.category = row.category_before_llm or "Browser"
            row.category_source = "rule"
            row.category_before_llm = None
        db.flush()
        return len(rows)

    result = db.execute(
        update(TrackedSession)
        .where(
            TrackedSession.app_name == key,
            TrackedSession.category_source == "llm_reviewed",
        )
        .values(
            category="Other",
            category_source="rule",
            category_before_llm=None,
        )
    )
    return result.rowcount  # type: ignore[union-attr]


def preview_impact(db: Session, key: str, key_type: str = "exe") -> dict:
    if key_type == "domain":
        rows = _domain_session_rows(db, key)
    else:
        rows = (
            db.query(TrackedSession)
            .filter(
                TrackedSession.app_name == key,
                TrackedSession.category == "Other",
                (TrackedSession.category_source.is_(None)) | (TrackedSession.category_source == "rule"),
            )
            .all()
        )
    total_minutes = 0
    starts: list[datetime] = []
    samples: list[dict] = []
    for r in rows:
        if r.start_time and r.end_time:
            dur = max(0, (r.end_time - r.start_time).total_seconds() / 60)
            total_minutes += dur
            starts.append(r.start_time)
            if len(samples) < 5:
                samples.append({
                    "date": r.start_time.isoformat(),
                    "title": r.window_title,
                    "minutes": round(dur, 1),
                })

    date_range = None
    if starts:
        date_range = [min(starts).isoformat(), max(starts).isoformat()]

    return {
        "count": len(rows),
        "total_minutes": round(total_minutes, 1),
        "date_range": date_range,
        "sample": samples,
    }
