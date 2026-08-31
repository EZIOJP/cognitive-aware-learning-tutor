"""Focus quality — context switches during on-plan blocks."""

from __future__ import annotations

from datetime import datetime
from typing import Any

PRODUCTIVE_THRESHOLD = 60


def _as_utc(dt: Any) -> datetime | None:
    """Normalize datetime or ISO string to timezone-aware datetime; skip invalid."""
    if dt is None or dt == "":
        return None
    if isinstance(dt, str):
        try:
            dt = datetime.fromisoformat(dt.replace("Z", "+00:00"))
        except (TypeError, ValueError):
            return None
    if not isinstance(dt, datetime):
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=datetime.now().astimezone().tzinfo)
    return dt


def compute_focus_quality(
    rows: list[Any],
    *,
    planned_intervals: list[tuple[Any, Any]],
    productive_threshold: int = PRODUCTIVE_THRESHOLD,
) -> dict[str, Any]:
    """Score 0–100 from context switches inside planned blocks."""
    if not planned_intervals or not rows:
        return {
            "score": 100,
            "switches": 0,
            "on_plan_minutes": 0,
            "low_score_minutes": 0,
            "label": "No on-plan data",
        }

    segments: list[tuple[datetime, datetime, str, int]] = []
    for row in rows:
        start = getattr(row, "start_time", None) or (row.get("start_time") if isinstance(row, dict) else None)
        end = getattr(row, "end_time", None) or (row.get("end_time") if isinstance(row, dict) else None)
        if not start or not end:
            continue
        start, end = _as_utc(start), _as_utc(end)
        if not start or not end or end <= start:
            continue
        if isinstance(row, dict):
            app = row.get("app_name") or row.get("exe") or "unknown"
            site = row.get("site") or row.get("domain")
            score = int(row.get("productivity_score") or 35)
        else:
            app = row.app_name or "unknown"
            site = getattr(row, "site", None)
            score = int(getattr(row, "productivity_score", None) or 35)
        key = (str(site).strip() if site else str(app).strip()) or "unknown"
        for ps, pe in planned_intervals:
            ps, pe = _as_utc(ps), _as_utc(pe)
            if not ps or not pe:
                continue
            seg_start = max(start, ps)
            seg_end = min(end, pe)
            if seg_end > seg_start:
                segments.append((seg_start, seg_end, key, score))

    if not segments:
        return {
            "score": 100,
            "switches": 0,
            "on_plan_minutes": 0,
            "low_score_minutes": 0,
            "label": "No overlap",
        }

    segments.sort(key=lambda x: x[0])
    on_plan_seconds = 0
    low_score_seconds = 0
    switches = 0
    prev_key: str | None = None

    for seg_start, seg_end, key, score in segments:
        dur = int((seg_end - seg_start).total_seconds())
        if dur <= 0:
            continue
        on_plan_seconds += dur
        if score < productive_threshold:
            low_score_seconds += dur
        if prev_key is not None and key != prev_key:
            switches += 1
        prev_key = key

    on_plan_min = on_plan_seconds / 60.0
    switch_rate = switches / max(1.0, on_plan_min / 30.0)
    penalty = min(100, int(round(switch_rate * 18 + (low_score_seconds / max(1, on_plan_seconds)) * 40)))
    score = max(0, min(100, 100 - penalty))

    if score >= 80:
        label = "Deep focus"
    elif score >= 60:
        label = "Solid focus"
    elif score >= 40:
        label = "Fragmented"
    else:
        label = "High switching"

    return {
        "score": score,
        "switches": switches,
        "on_plan_minutes": round(on_plan_min, 1),
        "low_score_minutes": round(low_score_seconds / 60.0, 1),
        "label": label,
    }
