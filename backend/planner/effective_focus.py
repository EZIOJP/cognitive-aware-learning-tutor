"""Effective focus minutes — overlap of planned blocks and productive tracked time."""

from __future__ import annotations

from datetime import datetime
from typing import Callable

from backend.behavior.category_scores import PRODUCTIVE_THRESHOLD

ScoreFn = Callable[[str | None], int]


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


def effective_focus_minutes(
    blocks,
    sessions,
    score_fn: ScoreFn,
    threshold: int = PRODUCTIVE_THRESHOLD,
) -> int:
    """Minutes inside a planner block where session score >= threshold."""
    total_seconds = 0.0
    for block in blocks:
        if not block.start_at or not block.end_at:
            continue
        for sess in sessions:
            if not sess.start_time or not sess.end_time:
                continue
            if score_fn(sess.category) < threshold:
                continue
            total_seconds += overlap_seconds(
                block.start_at,
                block.end_at,
                sess.start_time,
                sess.end_time,
            )
    return int(total_seconds // 60)


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
        if score_fn(sess.category) < threshold:
            continue
        total += int((sess.end_time - sess.start_time).total_seconds() // 60)
    return total
