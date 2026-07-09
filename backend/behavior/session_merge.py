"""Read-time merge of adjacent tracker sessions for cleaner UI (no DB writes)."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Sequence

from backend.behavior.tracker_ignore import is_ignored_app

CALENDAR_MERGE_GAP_SEC = 900  # 15 min — calendar overlay
CALENDAR_MIN_DURATION_SEC = 120  # drop sub-2-min noise on calendar


def _parse_dt(value: datetime | str | None) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None


def _same_merge_group(a: Any, b: Any) -> bool:
    app_a = getattr(a, "app_name", None) or a.get("app_name") if isinstance(a, dict) else None
    app_b = getattr(b, "app_name", None) or b.get("app_name") if isinstance(b, dict) else None
    cat_a = getattr(a, "category", None) or (a.get("category") if isinstance(a, dict) else None)
    cat_b = getattr(b, "category", None) or (b.get("category") if isinstance(b, dict) else None)
    return app_a == app_b and cat_a == cat_b


def _get_times(row: Any) -> tuple[datetime | None, datetime | None]:
    if isinstance(row, dict):
        return _parse_dt(row.get("start_time")), _parse_dt(row.get("end_time"))
    return _parse_dt(row.start_time), _parse_dt(row.end_time)


def filter_ignored_rows(rows: Sequence[Any]) -> list[Any]:
    """Drop keep-awake / utility apps from display pipelines."""
    out: list[Any] = []
    for row in rows:
        if isinstance(row, dict):
            exe = row.get("app_name") or row.get("exe") or ""
            title = row.get("window_title") or row.get("title") or ""
        else:
            exe = getattr(row, "app_name", None) or ""
            title = getattr(row, "window_title", None) or ""
        if is_ignored_app(str(exe), str(title)):
            continue
        out.append(row)
    return out


def merge_tracked_rows(rows: Sequence[Any], *, gap_seconds: int = 5) -> list[Any]:
    """Merge consecutive TrackedSession ORM rows or interval dicts."""
    if not rows:
        return []
    ordered = sorted(rows, key=lambda r: _get_times(r)[0] or datetime.min)
    merged: list[Any] = [ordered[0]]

    for row in ordered[1:]:
        prev = merged[-1]
        prev_start, prev_end = _get_times(prev)
        cur_start, cur_end = _get_times(row)
        if not prev_end or not cur_start:
            merged.append(row)
            continue
        gap = (cur_start - prev_end).total_seconds()
        if gap <= gap_seconds and _same_merge_group(prev, row):
            if isinstance(prev, dict) and isinstance(row, dict):
                prev["end_time"] = row["end_time"]
                prev["duration_seconds"] = int(
                    (_parse_dt(prev["end_time"]) - _parse_dt(prev["start_time"])).total_seconds()  # type: ignore[arg-type]
                )
                if row.get("window_title"):
                    prev["window_title"] = row["window_title"]
            else:
                prev.end_time = row.end_time  # type: ignore[union-attr]
                if getattr(row, "window_title", None):
                    prev.window_title = row.window_title  # type: ignore[union-attr]
        else:
            merged.append(row)

    return merged


def merge_for_calendar(rows: Sequence[Any]) -> list[Any]:
    """Aggressive merge + min duration for planner calendar actual overlay."""
    filtered = filter_ignored_rows(rows)
    merged = merge_tracked_rows(filtered, gap_seconds=CALENDAR_MERGE_GAP_SEC)
    out: list[Any] = []
    for row in merged:
        start, end = _get_times(row)
        if not start or not end:
            continue
        dur = (end - start).total_seconds()
        if dur < CALENDAR_MIN_DURATION_SEC:
            continue
        out.append(row)
    return out
