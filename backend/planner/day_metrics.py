"""Plan-locked day metrics: local day clip + interval unions.

Only on-plan productive time counts toward adherence / focus goals.
Off-plan productive time is drift (informational only).
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from backend.behavior.category_scores import PRODUCTIVE_THRESHOLD
from backend.planner.effective_focus import ScoreFn, _score, plan_adherence_pct
from backend.planner.service import _utc, local_day_bounds_utc

PLAN_BLOCK_STATUSES = frozenset({"scheduled", "in_progress", "done"})


def clip_interval(
    start: datetime,
    end: datetime,
    window_start: datetime,
    window_end: datetime,
) -> tuple[datetime, datetime] | None:
    s = max(_utc(start), _utc(window_start))
    e = min(_utc(end), _utc(window_end))
    if e <= s:
        return None
    return s, e


def merge_intervals(intervals: list[tuple[datetime, datetime]]) -> list[tuple[datetime, datetime]]:
    if not intervals:
        return []
    norm = sorted((_utc(a), _utc(b)) for a, b in intervals if _utc(b) > _utc(a))
    if not norm:
        return []
    merged: list[list[datetime]] = [[norm[0][0], norm[0][1]]]
    for s, e in norm[1:]:
        if s > merged[-1][1]:
            merged.append([s, e])
        else:
            merged[-1][1] = max(merged[-1][1], e)
    return [(a, b) for a, b in merged]


def union_seconds(intervals: list[tuple[datetime, datetime]]) -> float:
    return sum((e - s).total_seconds() for s, e in merge_intervals(intervals))


def subtract_intervals(
    segment: tuple[datetime, datetime],
    blockers: list[tuple[datetime, datetime]],
) -> list[tuple[datetime, datetime]]:
    """Return parts of segment not covered by any blocker interval."""
    remaining = [(_utc(segment[0]), _utc(segment[1]))]
    for b0, b1 in merge_intervals(blockers):
        next_rem: list[tuple[datetime, datetime]] = []
        for r0, r1 in remaining:
            if b1 <= r0 or b0 >= r1:
                next_rem.append((r0, r1))
                continue
            if r0 < b0:
                next_rem.append((r0, b0))
            if b1 < r1:
                next_rem.append((b1, r1))
        remaining = [(a, b) for a, b in next_rem if b > a]
    return remaining


def compute_day_metrics(
    day: date,
    blocks: list[Any],
    sessions: list[Any],
    score_fn: ScoreFn,
    *,
    threshold: int = PRODUCTIVE_THRESHOLD,
) -> dict[str, Any]:
    """Aggregate plan-locked metrics for one local calendar day."""
    day_start, day_end = local_day_bounds_utc(day)

    active_blocks = [
        b
        for b in blocks
        if getattr(b, "start_at", None)
        and getattr(b, "end_at", None)
        and str(getattr(b, "status", "") or "") in PLAN_BLOCK_STATUSES
        and _utc(b.start_at) < day_end
        and _utc(b.end_at) > day_start
    ]

    planned_intervals: list[tuple[datetime, datetime]] = []
    for b in active_blocks:
        clipped = clip_interval(b.start_at, b.end_at, day_start, day_end)
        if clipped:
            planned_intervals.append(clipped)
    planned_merged = merge_intervals(planned_intervals)
    planned_minutes = int(union_seconds(planned_merged) // 60)

    focus_intervals: list[tuple[datetime, datetime]] = []
    distraction_intervals: list[tuple[datetime, datetime]] = []
    productive_segments: list[tuple[datetime, datetime]] = []
    actual_seconds = 0.0
    session_count = 0

    for sess in sessions:
        if not getattr(sess, "start_time", None) or not getattr(sess, "end_time", None):
            continue
        clipped = clip_interval(sess.start_time, sess.end_time, day_start, day_end)
        if not clipped:
            continue
        session_count += 1
        seg_s, seg_e = clipped
        secs = (seg_e - seg_s).total_seconds()
        if secs < 2:
            continue
        actual_seconds += secs
        score = _score(score_fn, sess)
        productive = score >= threshold

        if productive:
            productive_segments.append((seg_s, seg_e))

        for p0, p1 in planned_merged:
            ov_s = max(seg_s, p0)
            ov_e = min(seg_e, p1)
            if ov_e <= ov_s:
                continue
            if productive:
                focus_intervals.append((ov_s, ov_e))
            else:
                distraction_intervals.append((ov_s, ov_e))

    on_plan_focus = int(union_seconds(focus_intervals) // 60)
    distraction_on_plan = int(union_seconds(distraction_intervals) // 60)
    productive_minutes = int(union_seconds(productive_segments) // 60)

    drift_intervals: list[tuple[datetime, datetime]] = []
    for seg in productive_segments:
        drift_intervals.extend(subtract_intervals(seg, planned_merged))
    off_plan_productive = int(union_seconds(drift_intervals) // 60)

    return {
        "day": day.isoformat(),
        "planned_minutes": planned_minutes,
        "actual_minutes": int(actual_seconds // 60),
        "productive_minutes": productive_minutes,
        "effective_focus_minutes": on_plan_focus,
        "on_plan_focus_minutes": on_plan_focus,
        "off_plan_productive_minutes": off_plan_productive,
        "distraction_on_plan_minutes": distraction_on_plan,
        "adherence_pct": plan_adherence_pct(on_plan_focus, planned_minutes),
        "block_count": len(active_blocks),
        "session_count": session_count,
    }
