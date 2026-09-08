"""Devotion ↔ calendar block sync."""

from __future__ import annotations

from datetime import date, datetime

from backend.behavior.calt_desktop.planner_data import blocks_for_day
from backend.planner.service import local_tz


def _is_spiritual_block(block: dict) -> bool:
    cat = str(block.get("category") or "").lower()
    title = str(block.get("title") or "").lower()
    if cat == "spiritual":
        return True
    return any(k in title for k in ("bible", "proverbs", "psalm", "prayer", "devotion", "hymn"))


def devotion_slot_for_block(block: dict) -> str | None:
    title = str(block.get("title") or "").lower()
    if "morning" in title or "lord" in title:
        return "morning"
    if "proverbs" in title or "psalm" in title or "afternoon" in title:
        return "afternoon"
    if "evening" in title or "hymn" in title or "praise" in title:
        return "evening"
    try:
        start = datetime.fromisoformat(str(block["start_at"]).replace("Z", "+00:00")).astimezone(local_tz())
        h = start.hour
        if h < 10:
            return "morning"
        if h < 17:
            return "afternoon"
        return "evening"
    except (ValueError, KeyError):
        return None


def spiritual_blocks_today(user_id: int, *, day: date | None = None) -> list[dict]:
    day = day or date.today()
    return [b for b in blocks_for_day(user_id, day) if _is_spiritual_block(b)]


def mark_devotion_for_block(user_id: int, block: dict) -> str:
    """Mark devotion done for block's slot; returns status."""
    slot = devotion_slot_for_block(block)
    if not slot:
        return "Not a devotion block"
    try:
        from backend.bible import store as bible_store

        bible_store.mark_devotion_done(user_id, slot=slot)
        return f"Marked {slot} devotion done"
    except Exception as exc:  # noqa: BLE001
        return str(exc)


def devotion_status_for_spine(user_id: int) -> dict[str, bool]:
    morning_ok = False
    afternoon_ok = False
    evening_ok = False
    try:
        from backend.bible import store as bible_store

        bible = bible_store.summary(user_id)
        chapters = list(bible.get("chapters_completed_today") or [])
        goal = bible.get("chapter_goal") or {}
        morning_ok = bool(goal.get("met")) or len(chapters) >= 1
        devo = bible_store.devotion_summary(user_id)
        afternoon_ok = bool((devo.get("afternoon") or {}).get("done"))
        evening_ok = bool((devo.get("evening") or {}).get("done"))
    except Exception:  # noqa: BLE001
        pass
    return {"morning": morning_ok, "afternoon": afternoon_ok, "evening": evening_ok}
