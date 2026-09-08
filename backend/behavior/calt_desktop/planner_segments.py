"""Planner hour segments — port of web planHourSegments.ts."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Any


def _day_key(d: date) -> str:
    return d.isoformat()


def _parse_iso(iso: str) -> datetime | None:
    raw = (iso or "").replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(raw)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone()


def plan_block_to_hour_segs(block: dict[str, Any], day: date) -> list[dict[str, Any]]:
    """Split one planner block into per-hour segments (minute axis 0–60)."""
    day_k = _day_key(day)
    start = _parse_iso(str(block.get("start_at") or ""))
    end = _parse_iso(str(block.get("end_at") or ""))
    if start is None or end is None or end <= start:
        return []

    out: list[dict[str, Any]] = []
    cursor = start.replace(second=0, microsecond=0)
    guard = 0
    while cursor < end and guard < 48:
        guard += 1
        if _day_key(cursor.date()) != day_k:
            cursor = (cursor + timedelta(hours=1)).replace(minute=0, second=0, microsecond=0)
            continue
        hour = cursor.hour
        hour_start = cursor.replace(minute=0, second=0, microsecond=0)
        hour_end = hour_start + timedelta(hours=1)

        seg_start = max(start, hour_start)
        seg_end = min(end, hour_end)
        if seg_end <= seg_start:
            cursor = hour_end
            continue

        start_min = max(0, min(59, seg_start.minute))
        end_min = 60 if seg_end >= hour_end else max(start_min + 1, min(60, seg_end.minute))

        out.append(
            {
                "block_id": int(block.get("id") or 0),
                "title": str(block.get("title") or ""),
                "category": str(block.get("category") or "study"),
                "color": block.get("color"),
                "hour": hour,
                "start_min": start_min,
                "end_min": end_min,
                "seam_left": start < hour_start,
                "seam_right": end > hour_end,
                "is_draft": bool(block.get("isDraft") or block.get("is_draft")),
                "status": str(block.get("status") or "scheduled"),
                "start_at": block.get("start_at"),
                "end_at": block.get("end_at"),
                "planned_minutes": block.get("planned_minutes"),
            }
        )
        cursor = hour_end
    return out


def plan_blocks_to_hour_segs(blocks: list[dict[str, Any]], day: date) -> list[dict[str, Any]]:
    segs: list[dict[str, Any]] = []
    for b in blocks:
        segs.extend(plan_block_to_hour_segs(b, day))
    return segs


def segs_by_hour(segs: list[dict[str, Any]]) -> dict[int, list[dict[str, Any]]]:
    out: dict[int, list[dict[str, Any]]] = {h: [] for h in range(24)}
    for s in segs:
        h = int(s.get("hour") or 0)
        if 0 <= h < 24:
            out[h].append(s)
    return out
