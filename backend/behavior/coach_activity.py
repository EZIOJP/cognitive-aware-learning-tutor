"""Browser activity summaries for the AI coach — titles, YouTube, domains."""

from __future__ import annotations

import csv
import json
import re
from collections import Counter
from datetime import UTC, date, datetime, timedelta
from typing import Any

from sqlalchemy.orm import Session

from backend.models import Reading, ReadingDefinition, User
from backend.paths import DATA_LOGS_DIR

_STUDY_TITLE_HINTS = (
    "tutorial",
    "lecture",
    "course",
    "lesson",
    "python",
    "data science",
    "machine learning",
    "statistics",
    "gre",
    "algebra",
    "calculus",
    "leetcode",
    "interview",
    "curriculum",
    "academy",
    "edx",
    "khan",
)
_STUDY_DOMAINS = (
    "scaler.com",
    "coursera.org",
    "udemy.com",
    "khanacademy.org",
    "leetcode.com",
    "arxiv.org",
    "scholar.google",
    "youtube.com",
    "music.youtube.com",
    "notion.so",
    "github.com",
    "stackoverflow.com",
)
_SKIP_DOMAINS = ("newtab", "chrome://", "edge://", "about:blank")


def _infer_intent(entry: dict[str, Any]) -> str:
    domain = str(entry.get("domain") or "").lower()
    title = str(entry.get("title") or entry.get("page_title") or "").lower()
    video = str(entry.get("video_title") or "").lower()
    category = str(entry.get("category") or "")

    if any(d in domain for d in ("netflix", "twitch", "disneyplus", "primevideo")):
        return "entertainment_streaming"
    if entry.get("site") == "youtube" or "youtube" in domain:
        hay = f"{video} {title}"
        if any(h in hay for h in _STUDY_TITLE_HINTS):
            return "study_video"
        if entry.get("video_watched_percent", 0) >= 50:
            return "video_active"
        return "video_or_music"
    if any(d in domain for d in _STUDY_DOMAINS[:5]):
        return "study_course"
    if any(d in domain for d in ("github", "stackoverflow", "arxiv", "scholar")):
        return "study_research"
    if domain in ("localhost", "127.0.0.1") or title.startswith("cognitive-aware"):
        return "study_app"
    if category in ("Dev / Docs", "Research", "Coursework", "Knowledge Work"):
        return "productive_browsing"
    if category in ("Social Media", "Gaming", "Shopping"):
        return "distraction_risk"
    if category == "Video / Streaming":
        return "video_or_music"
    return "general_browsing"


def _normalize_event(raw: dict[str, Any]) -> dict[str, Any] | None:
    domain = str(raw.get("domain") or "")
    if any(skip in domain for skip in _SKIP_DOMAINS):
        return None

    title = (
        raw.get("video_title")
        or raw.get("page_title")
        or raw.get("title")
        or raw.get("active_item")
        or ""
    )
    title = str(title).strip()
    if not title or title.lower() in {"untitled", "new tab", "netflix"}:
        if not raw.get("video_title") and not raw.get("site"):
            return None

    entry: dict[str, Any] = {
        "type": raw.get("type") or "event",
        "domain": domain,
        "title": title[:200],
        "category": raw.get("category"),
        "url_hint": str(raw.get("url") or "")[:120],
    }

    if raw.get("site") == "youtube" or "youtube" in domain:
        entry["site"] = "youtube"
        if raw.get("video_title"):
            entry["video_title"] = str(raw["video_title"])[:200]
        if raw.get("channel_name"):
            entry["channel"] = str(raw["channel_name"])[:80]
        if raw.get("video_watched_percent") is not None:
            entry["video_watched_percent"] = raw.get("video_watched_percent")
        if raw.get("playlist_title"):
            entry["playlist"] = str(raw["playlist_title"])[:120]
        if raw.get("current_chapter"):
            entry["chapter"] = str(raw["current_chapter"])[:80]

    if raw.get("site") == "scalar":
        entry["site"] = "scalar"
        if raw.get("active_item"):
            entry["active_section"] = str(raw["active_item"])[:120]
        if raw.get("completion_percent") is not None:
            entry["completion_percent"] = raw.get("completion_percent")

    if raw.get("duration_seconds"):
        try:
            entry["duration_seconds"] = int(float(raw["duration_seconds"]))
        except (TypeError, ValueError):
            pass

    if raw.get("interaction_mode"):
        entry["interaction"] = raw.get("interaction_mode")

    preview = raw.get("scraped_text_preview")
    if preview and len(str(preview)) > 20:
        entry["page_preview"] = str(preview)[:180]

    entry["intent"] = _infer_intent({**raw, **entry})
    return entry


def _load_payloads_db(db: Session, user_id: int, *, hours: int = 48, limit: int = 400) -> list[dict]:
    defn = db.query(ReadingDefinition).filter(ReadingDefinition.slug == "browser_event").first()
    if not defn:
        return []

    since = datetime.now(UTC) - timedelta(hours=hours)
    rows = (
        db.query(Reading)
        .filter(
            Reading.user_id == user_id,
            Reading.definition_id == defn.id,
            Reading.recorded_at >= since,
        )
        .order_by(Reading.recorded_at.desc())
        .limit(limit)
        .all()
    )
    out: list[dict] = []
    for row in rows:
        try:
            payload = json.loads(row.value_json) if row.value_json else {}
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            out.append(payload)
    return out


def _load_payloads_csv(day: date | None = None, *, limit: int = 400) -> list[dict]:
    if day is None:
        day = date.today()
    path = DATA_LOGS_DIR / f"DSC_browser_behavior_{day.isoformat()}.csv"
    if not path.is_file():
        candidates = sorted(DATA_LOGS_DIR.glob("DSC_browser_behavior_*.csv"), reverse=True)
        if not candidates:
            return []
        path = candidates[0]
    rows: list[dict] = []
    with open(path, encoding="utf-8", errors="replace") as f:
        for row in csv.DictReader(f):
            row["type"] = row.get("type") or "event"
            rows.append(row)
            if len(rows) >= limit:
                break
    return list(reversed(rows))


def _matches_keywords(entry: dict[str, Any], keywords: list[str]) -> bool:
    if not keywords:
        return True
    hay = " ".join(
        str(entry.get(k, ""))
        for k in (
            "title",
            "video_title",
            "domain",
            "channel",
            "playlist",
            "chapter",
            "page_preview",
            "active_section",
            "url_hint",
        )
    ).lower()
    return any(k in hay for k in keywords)


def _dedupe_entries(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for entry in entries:
        key = "|".join(
            [
                entry.get("domain", ""),
                entry.get("video_title") or entry.get("title", ""),
                entry.get("type", ""),
            ]
        )
        if key in seen:
            continue
        seen.add(key)
        out.append(entry)
    return out


def browser_activity_for_coach(
    db: Session,
    user_id: int,
    query: str = "",
    *,
    limit: int = 20,
) -> dict[str, Any]:
    """Summarize extension/browser signals for the study coach."""
    keywords = re.findall(r"[a-z0-9]{3,}", (query or "").lower())[:12]

    payloads = _load_payloads_db(db, user_id)
    source = "database"
    linked_user = "self"

    if not payloads:
        demo = db.query(User).filter(User.username == "demo").first()
        if demo and demo.id != user_id:
            payloads = _load_payloads_db(db, demo.id)
            if payloads:
                linked_user = "demo_extension_default"

    csv_payloads = _load_payloads_csv(date.today())
    if csv_payloads:
        if not payloads:
            payloads = csv_payloads
            source = "csv_fallback"
            linked_user = "local_machine"
        elif keywords:
            payloads = payloads + csv_payloads

    normalized: list[dict[str, Any]] = []
    for raw in payloads:
        entry = _normalize_event(raw)
        if entry:
            normalized.append(entry)

    normalized = _dedupe_entries(normalized)
    filtered = [e for e in normalized if _matches_keywords(e, keywords)] if keywords else normalized
    keyword_fallback = False
    if keywords and not filtered and normalized:
        filtered = normalized
        keyword_fallback = True

    if keywords and not keyword_fallback:
        filtered.sort(
            key=lambda e: sum(1 for k in keywords if k in json.dumps(e).lower()),
            reverse=True,
        )
    else:
        intent_rank = {
            "study_course": 10,
            "study_video": 9,
            "study_app": 8,
            "study_research": 7,
            "productive_browsing": 6,
            "video_active": 4,
            "general_browsing": 2,
            "video_or_music": 1,
            "entertainment_streaming": 0,
            "distraction_risk": 0,
        }
        filtered.sort(key=lambda e: intent_rank.get(str(e.get("intent")), 1), reverse=True)

    recent = filtered[:limit]
    intents = Counter(str(e.get("intent")) for e in filtered)
    study_titles = [
        e.get("video_title") or e.get("title")
        for e in filtered
        if str(e.get("intent", "")).startswith("study")
    ][:8]

    return {
        "source": source,
        "linked_user": linked_user,
        "events_parsed": len(filtered),
        "keyword_fallback": keyword_fallback,
        "intent_breakdown": dict(intents.most_common(8)),
        "study_signals": study_titles,
        "recent": recent,
        "note": (
            "Categories from the extension are rough guesses. Trust page/video titles and domains more "
            "than category labels. YouTube/Scalar/scraper fields are the most reliable study signals."
        ),
    }
