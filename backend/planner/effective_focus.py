"""Effective focus minutes — overlap of planned blocks and productive tracked time."""

from __future__ import annotations

import inspect
from datetime import datetime
from typing import Any, Callable

from backend.behavior.category_scores import PRODUCTIVE_THRESHOLD

# Accept either category string or full session row
ScoreFn = Callable[[Any], int]


def overlap_seconds(
    a0: datetime,
    a1: datetime,
    b0: datetime,
    b1: datetime,
) -> float:
    start = max(a0, b0)
    end = min(a1, b1)
    if end <= start:
        return 0.0
    return (end - start).total_seconds()


def _score(score_fn: ScoreFn, sess: Any) -> int:
    """Support legacy score_fn(category) and new score_fn(session)."""
    cat = sess.category if hasattr(sess, "category") else None
    prefer_session = False
    try:
        params = list(inspect.signature(score_fn).parameters.values())
        if params and params[0].name in ("sess", "session", "row", "s"):
            prefer_session = True
    except (TypeError, ValueError):
        prefer_session = False

    if prefer_session:
        try:
            return int(score_fn(sess))
        except TypeError:
            return int(score_fn(cat))

    try:
        return int(score_fn(cat))
    except TypeError:
        return int(score_fn(sess))


def effective_focus_minutes(
    blocks,
    sessions,
    score_fn: ScoreFn,
    threshold: int = PRODUCTIVE_THRESHOLD,
) -> int:
    """Minutes inside a planner block where session score >= threshold (union, no double-count)."""
    from backend.planner.day_metrics import union_seconds

    intervals: list[tuple[datetime, datetime]] = []
    for block in blocks:
        if not block.start_at or not block.end_at:
            continue
        for sess in sessions:
            if not sess.start_time or not sess.end_time:
                continue
            if _score(score_fn, sess) < threshold:
                continue
            secs = overlap_seconds(
                block.start_at,
                block.end_at,
                sess.start_time,
                sess.end_time,
            )
            if secs <= 0:
                continue
            start = max(block.start_at, sess.start_time)
            end = min(block.end_at, sess.end_time)
            intervals.append((start, end))
    return int(union_seconds(intervals) // 60)


def productive_minutes_from_sessions(
    sessions,
    score_fn: ScoreFn,
    threshold: int = PRODUCTIVE_THRESHOLD,
) -> int:
    """Any tracked minutes with score >= threshold."""
    total = 0
    for sess in sessions:
        if not sess.start_time or not sess.end_time:
            continue
        if _score(score_fn, sess) < threshold:
            continue
        total += int((sess.end_time - sess.start_time).total_seconds() // 60)
    return total


def plan_adherence_pct(effective_focus: int, planned_minutes: int) -> float | None:
    """Share of planned time that was productive focus (0–100). Never >100.

    Do NOT use raw tracked minutes / planned — that counts outside-plan screen
    time and can show absurd values like 370%.
    """
    if not planned_minutes:
        return None
    return round(min(100.0, 100.0 * max(0, effective_focus) / planned_minutes), 1)
