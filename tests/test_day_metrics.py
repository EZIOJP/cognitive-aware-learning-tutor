"""Tests for plan-locked day metrics (union, clip, drift)."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from backend.planner.day_metrics import (
    clip_interval,
    compute_day_metrics,
    union_seconds,
)
from backend.planner.effective_focus import plan_adherence_pct
from backend.planner.llm_propose import _adherence_load_scale


class _Block:
    def __init__(self, start, end, status="scheduled"):
        self.start_at = start
        self.end_at = end
        self.status = status
        self.planned_minutes = int((end - start).total_seconds() // 60)


class _Sess:
    def __init__(self, start, end, score=80, category="IDE / Code Editor"):
        self.start_time = start
        self.end_time = end
        self.category = category
        self.app_name = "Code.exe"
        self.window_title = "study"


def test_union_merges_overlapping_intervals():
    t0 = datetime(2026, 7, 19, 10, 0, tzinfo=timezone.utc)
    a = (t0, t0 + timedelta(hours=1))
    b = (t0 + timedelta(minutes=30), t0 + timedelta(hours=2))
    assert union_seconds([a, b]) == 2 * 3600


def test_overlapping_blocks_planned_is_union_not_sum():
    day = date(2026, 7, 19)
    # Force local day window by using UTC-aligned blocks well inside a UTC day
    # compute_day_metrics uses local_day_bounds — pick blocks relative to that.
    from backend.planner.service import local_day_bounds_utc

    start, end = local_day_bounds_utc(day)
    mid = start + timedelta(hours=10)
    b1 = _Block(mid, mid + timedelta(hours=1))
    b2 = _Block(mid + timedelta(minutes=30), mid + timedelta(hours=2))
    m = compute_day_metrics(day, [b1, b2], [], lambda s: 80)
    assert m["planned_minutes"] == 120  # union 10:00–12:00


def test_off_plan_productive_does_not_raise_adherence():
    from backend.planner.service import local_day_bounds_utc

    day = date(2026, 7, 19)
    start, _ = local_day_bounds_utc(day)
    block_start = start + timedelta(hours=9)
    block = _Block(block_start, block_start + timedelta(hours=1))
    # Productive session entirely outside the plan
    drift = _Sess(
        block_start + timedelta(hours=3),
        block_start + timedelta(hours=5),
        score=90,
    )
    m = compute_day_metrics(day, [block], [drift], lambda s: 90)
    assert m["productive_minutes"] == 120
    assert m["productive_label"] == "2 hours"
    assert m["off_plan_productive_minutes"] == 120
    assert m["off_plan_productive_label"] == "2 hours"
    assert m["adherence_pct"] == 0.0


def test_on_plan_productive_raises_focus_and_adherence():
    from backend.planner.service import local_day_bounds_utc

    day = date(2026, 7, 19)
    start, _ = local_day_bounds_utc(day)
    block_start = start + timedelta(hours=9)
    block = _Block(block_start, block_start + timedelta(hours=1))
    sess = _Sess(block_start, block_start + timedelta(minutes=30), score=90)
    m = compute_day_metrics(day, [block], [sess], lambda s: 90)
    assert m["on_plan_focus_minutes"] == 30
    assert m["adherence_pct"] == 50.0
    assert m["off_plan_productive_minutes"] == 0


def test_cross_midnight_clip_splits_across_days():
    from backend.planner.service import local_day_bounds_utc

    day_a = date(2026, 7, 18)
    day_b = date(2026, 7, 19)
    _, end_a = local_day_bounds_utc(day_a)
    # Block spanning last hour of day_a into first hour of day_b
    block = _Block(end_a - timedelta(hours=1), end_a + timedelta(hours=1))
    m_a = compute_day_metrics(day_a, [block], [], lambda s: 80)
    m_b = compute_day_metrics(day_b, [block], [], lambda s: 80)
    assert m_a["planned_minutes"] == 60
    assert m_b["planned_minutes"] == 60


def test_clip_interval_basic():
    w0 = datetime(2026, 7, 19, 0, 0, tzinfo=timezone.utc)
    w1 = w0 + timedelta(days=1)
    s = w0 - timedelta(hours=1)
    e = w0 + timedelta(hours=2)
    clipped = clip_interval(s, e, w0, w1)
    assert clipped is not None
    assert clipped[0] == w0
    assert (clipped[1] - clipped[0]).total_seconds() == 2 * 3600


def test_adherence_load_scale_caps_and_prefers_pct():
    export = {
        "by_day": [
            {"planned_minutes": 120, "adherence_pct": 150.0, "effective_focus_minutes": 200},
            {"planned_minutes": 120, "adherence_pct": 40.0},
        ]
    }
    scale, avg = _adherence_load_scale(export)
    assert avg is not None
    assert avg <= 100.0
    # avg of capped 100 and 40 = 70 → 0.9
    assert scale == 0.9


def test_plan_adherence_pct_never_uses_off_plan():
    assert plan_adherence_pct(0, 60) == 0.0
    assert plan_adherence_pct(30, 60) == 50.0
