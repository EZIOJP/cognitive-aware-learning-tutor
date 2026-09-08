"""Task-aware gate profiles — switch study/free based on active calendar block."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from backend.behavior.calt_desktop.planner_data import blocks_for_day
from backend.planner.service import local_tz


def _category_mode(category: str, title: str) -> str:
    c = (category or "").strip().lower()
    t = (title or "").strip().lower()
    if c == "spiritual" or "bible" in t or "prayer" in t or "proverbs" in t or "psalm" in t:
        return "spiritual"
    if c in ("study", "coursework", "work") or "scaler" in t:
        return "study"
    if c in ("break", "free", "reward") or "free time" in t:
        return "free"
    if c == "food" or any(x in t for x in ("breakfast", "lunch", "dinner", "meal")):
        return "food"
    if "sleep" in t or "get ready to sleep" in t:
        return "sleep_prep"
    return "routine"


def gate_profile_for_block(block: dict[str, Any]) -> dict[str, Any]:
    """Map block → gate action hints (study nudge, free override, etc.)."""
    cat = str(block.get("category") or "")
    title = str(block.get("title") or "")
    mode = _category_mode(cat, title)
    task = block.get("study_task") if isinstance(block.get("study_task"), dict) else None
    if task:
        return {
            "mode": "study",
            "label": str(task.get("title") or title),
            "allow_hosts": list(task.get("allowHosts") or []),
            "block_categories": list(task.get("blockCategories") or []),
            "minutes": int(task.get("minutes") or 60),
        }
    profiles = {
        "study": {
            "mode": "study",
            "label": title,
            "allow_hosts": ["scaler.com", "colab.research.google.com", "github.com"],
            "block_categories": ["Gaming", "Video Streaming", "Social Media", "Entertainment"],
        },
        "spiritual": {
            "mode": "spiritual",
            "label": title,
            "allow_hosts": ["bible.com", "youversion.com", "biblegateway.com"],
            "block_categories": ["Gaming", "Video Streaming", "Social Media"],
        },
        "free": {"mode": "free", "label": title, "allow_hosts": [], "block_categories": []},
        "food": {"mode": "food", "label": title, "allow_hosts": [], "block_categories": []},
        "sleep_prep": {
            "mode": "sleep_prep",
            "label": title,
            "allow_hosts": [],
            "block_categories": ["Social Media", "Gaming", "Video Streaming"],
        },
        "routine": {"mode": "routine", "label": title, "allow_hosts": [], "block_categories": []},
    }
    return profiles.get(mode, profiles["routine"])


def active_block_now(user_id: int, *, now: datetime | None = None) -> dict[str, Any] | None:
    if not user_id:
        return None
    dt = now or datetime.now(local_tz())
    if dt.tzinfo is None:
        dt = dt.astimezone(local_tz())
    day = dt.date()
    for block in blocks_for_day(user_id, day):
        try:
            start = datetime.fromisoformat(str(block["start_at"]).replace("Z", "+00:00"))
            end = datetime.fromisoformat(str(block["end_at"]).replace("Z", "+00:00"))
        except (ValueError, KeyError):
            continue
        if start.tzinfo is None:
            start = start.replace(tzinfo=local_tz())
        if end.tzinfo is None:
            end = end.replace(tzinfo=local_tz())
        start = start.astimezone(local_tz())
        end = end.astimezone(local_tz())
        if start <= dt < end:
            out = dict(block)
            out["gate_profile"] = gate_profile_for_block(block)
            return out
    return None


def apply_gate_for_active_block(user_id: int, *, now: datetime | None = None) -> str | None:
    """Arm study nudge or free override for current block. Returns status line."""
    block = active_block_now(user_id, now=now)
    if not block:
        return None
    profile = block.get("gate_profile") or gate_profile_for_block(block)
    mode = str(profile.get("mode") or "")
    title = str(profile.get("label") or block.get("title") or "block")
    try:
        start = datetime.fromisoformat(str(block["start_at"]).replace("Z", "+00:00"))
        end = datetime.fromisoformat(str(block["end_at"]).replace("Z", "+00:00"))
        mins = max(15, int((end - start).total_seconds() // 60))
    except (ValueError, KeyError):
        mins = 45

    if mode == "free":
        from backend.behavior.browser_gate_policy import set_free_override

        set_free_override(minutes=mins)
        return f"Gate FREE for {title} ({mins}m)"
    if mode in ("study", "spiritual", "sleep_prep"):
        from backend.behavior.study_mode_nudge import arm_study_mode_nudge

        arm_study_mode_nudge(minutes=mins, reason=f"block:{title[:40]}")
        return f"Gate STUDY for {title} ({mins}m)"
    return None


def next_block(user_id: int, *, now: datetime | None = None) -> dict[str, Any] | None:
    if not user_id:
        return None
    dt = now or datetime.now(local_tz())
    day = dt.date()
    upcoming = None
    for block in blocks_for_day(user_id, day):
        try:
            start = datetime.fromisoformat(str(block["start_at"]).replace("Z", "+00:00"))
        except (ValueError, KeyError):
            continue
        if start.astimezone(local_tz()) > dt.astimezone(local_tz()):
            upcoming = block
            break
    return upcoming
