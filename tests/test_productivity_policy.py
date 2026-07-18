"""Tests for productivity policy scoring + export filter + LLM propose parse."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from unittest.mock import patch

from backend.behavior.productivity_policy import (
    DEFAULT_BLOCKED_CATEGORIES,
    default_policy_dict,
    resolve_productivity_score,
    resolve_session_score,
)
from backend.planner.effective_focus import effective_focus_minutes
from backend.planner.llm_propose import _extract_json, propose_week_from_export
from backend.planner.week_export import filter_export_payload


def test_blocked_gaming_scores_zero():
    policy = default_policy_dict()
    assert "Gaming" in DEFAULT_BLOCKED_CATEGORIES
    scores = {"Gaming": 10, "Coding Practice": 90}
    assert resolve_productivity_score("Gaming", scores, policy) == 0
    assert resolve_productivity_score("Coding Practice", scores, policy) >= 60


def test_session_override_forces_productive():
    policy = default_policy_dict()
    scores = {"Gaming": 10}

    class Sess:
        category = "Gaming"
        app_name = "steam.exe"
        window_title = None
        override_productive = True

    assert resolve_session_score(Sess(), scores, policy) >= 60

    Sess.override_productive = False
    assert resolve_session_score(Sess(), scores, policy) == 0


def test_effective_focus_ignores_gaming_on_plan():
    policy = default_policy_dict()
    scores = {"Gaming": 10, "IDE / Code Editor": 90}
    start = datetime(2026, 7, 14, 10, 0, tzinfo=timezone.utc)
    end = start + timedelta(hours=2)

    class Block:
        start_at = start
        end_at = end

    class GameSess:
        category = "Gaming"
        app_name = "game.exe"
        window_title = None
        override_productive = None
        start_time = start
        end_time = end

    def score_fn(sess):
        return resolve_session_score(sess, scores, policy)

    assert effective_focus_minutes([Block()], [GameSess()], score_fn, threshold=60) == 0


def test_filter_export_payload_include():
    payload = {
        "export_version": "1.1",
        "exported_at": "x",
        "purpose": "p",
        "range": {"start": "a", "end": "b", "days": 7},
        "policy_snapshot": {"threshold": 60},
        "summary": {"peak_hours": [10]},
        "weekday_patterns": {"mon": {}},
        "suggested_timetable_hints": ["h"],
        "by_day": [{"date": "2026-07-14", "planned_blocks": [], "productive_minutes": 30}],
    }
    slim = filter_export_payload(payload, include={"summary", "policy"})
    assert "summary" in slim
    assert "policy_snapshot" in slim
    assert "by_day" not in slim


def test_extract_json_fenced():
    data = _extract_json('```json\n{"blocks": [], "rationale": "ok"}\n```')
    assert data["rationale"] == "ok"


def test_propose_week_fallback_when_llm_off():
    export = {
        "summary": {"peak_hours": [9, 15]},
        "weekday_patterns": {},
        "suggested_timetable_hints": [],
        "policy_snapshot": default_policy_dict(),
    }
    with patch("backend.planner.llm_propose.ollama_generate", return_value=None):
        result = propose_week_from_export(export, week_start=date(2026, 7, 13))
    assert result["used_llm"] is False
    assert len(result["blocks"]) >= 1
    assert result["blocks"][0]["start_at"]


def test_smart_rules_avoid_routine_overlap_and_use_focus_target():
    from datetime import datetime, timedelta

    from backend.planner.llm_propose import propose_week_from_export

    export = {
        "summary": {
            "peak_hours": [10, 14],
            "top_categories": [{"category": "Coding Practice", "minutes": 120}],
            "quietest_weekday": "sun",
        },
        "weekday_patterns": {
            "mon": {
                "days_sampled": 2,
                "avg_productive_minutes": 180,
                "peak_hours": [10, 15],
            },
        },
        "suggested_timetable_hints": [],
        "policy_snapshot": default_policy_dict(),
    }
    routines = [
        {
            "title": "Gym",
            "category": "personal",
            "start_time": "10:00",
            "end_time": "11:00",
            "days": ["mon"],
            "enabled": True,
        }
    ]
    goals = (
        "Complete Scaler AI/ML. Daily effective-focus target: 2h. "
        "Weekly target: 10h. Reward: games after focus."
    )
    # Propose clamps past days to today — use upcoming Monday.
    today = date.today()
    monday = today + timedelta(days=(7 - today.weekday()) % 7)
    result = propose_week_from_export(
        export,
        goals=goals,
        range_start=monday,
        horizon_days=1,
        use_llm=False,
        mode="smart",
        routines=routines,
    )
    assert result["used_llm"] is False
    assert "gap" in result["rationale"].lower() or "Smart" in result["rationale"]

    gym = next(b for b in result["blocks"] if b["title"] == "Gym")
    study = [b for b in result["blocks"] if b.get("source") == "study"]
    assert study, "expected study blocks besides routine"

    def _span(b):
        return datetime.fromisoformat(b["start_at"]), datetime.fromisoformat(b["end_at"])

    g0, g1 = _span(gym)
    for b in study:
        s0, s1 = _span(b)
        assert not (s0 < g1 and g0 < s1), f"study overlaps gym: {b}"

    study_minutes = sum(
        int((datetime.fromisoformat(b["end_at"]) - datetime.fromisoformat(b["start_at"])).total_seconds() // 60)
        for b in study
    )
    assert study_minutes >= 90  # ~2h target (± packing)


def test_free_gaps_respect_busy():
    from backend.planner.llm_propose import _free_gaps, _pack_gaps_with_goals

    gaps = _free_gaps([(10 * 60, 11 * 60)], day_start=8 * 60, day_end=18 * 60, min_gap=45)
    assert gaps[0] == (8 * 60, 10 * 60)
    assert gaps[1][0] == 11 * 60
    packed = _pack_gaps_with_goals(
        gaps,
        target_min=120,
        slices=[("A", "Coding Practice"), ("B", "AI / ML")],
        peaks=[9, 14],
    )
    assert packed
    study_min = sum(e - s for s, e, _t, c in packed if c != "break")
    assert study_min >= 90


def test_never_schedules_gaming_as_study_and_hits_daily_hours():
    from datetime import datetime

    from backend.planner.llm_propose import _parse_goal_slices, propose_week_from_export

    goals = (
        "Complete the Scaler AI/ML course — daily lessons + practice before entertainment. "
        "Daily effective-focus target: 4h. Weekly target: 24h. Reward: games after focus."
    )
    slices = _parse_goal_slices(
        goals,
        {
            "summary": {
                "top_categories": [
                    {"category": "Gaming", "minutes": 900},
                    {"category": "Entertainment", "minutes": 400},
                ]
            }
        },
    )
    assert slices
    assert all("gam" not in t.lower() and "gam" not in c.lower() for t, c in slices)
    assert any("scaler" in t.lower() or "ai" in t.lower() or "practice" in t.lower() for t, c in slices)

    export = {
        "summary": {
            "peak_hours": [10, 14, 16],
            "top_categories": [{"category": "Gaming", "minutes": 500}],
        },
        "weekday_patterns": {},
    }
    routines = [
        {
            "title": "Breakfast",
            "category": "food",
            "start_time": "08:00",
            "end_time": "08:30",
            "days": ["sat"],
            "enabled": True,
        }
    ]
    result = propose_week_from_export(
        export,
        goals=goals,
        range_start=date(2026, 7, 18),
        horizon_days=1,
        use_llm=False,
        mode="smart",
        routines=routines,
    )
    study = [b for b in result["blocks"] if b.get("source") == "study"]
    assert study
    for b in study:
        blob = f"{b['title']} {b['category']}".lower()
        assert "gam" not in blob, b
        assert "entertain" not in blob, b
    mins = sum(
        int(
            (datetime.fromisoformat(b["end_at"]) - datetime.fromisoformat(b["start_at"])).total_seconds()
            // 60
        )
        for b in study
    )
    assert mins >= 210, f"expected ~4h study, got {mins}m"  # allow small shortfall


def test_pack_prefers_50m_chunks_and_inserts_breaks():
    from backend.planner.llm_propose import _pack_gaps_with_goals

    # One long free morning — should pack ~50m study with breaks, stop at 240m
    gaps = [(8 * 60, 18 * 60)]
    packed = _pack_gaps_with_goals(
        gaps,
        target_min=240,
        slices=[("Scaler — daily lessons", "Coursework (Browser)")],
        peaks=[10],
        preferred_chunk=50,
    )
    study = [(s, e) for s, e, _t, c in packed if c != "break"]
    breaks = [x for x in packed if x[3] == "break"]
    assert study
    assert breaks, "expected short breaks between study chunks"
    study_min = sum(e - s for s, e in study)
    assert study_min <= 240
    assert study_min >= 220
    # Most chunks near 50m (allow final short slice)
    near_50 = sum(1 for s, e in study if 40 <= (e - s) <= 55)
    assert near_50 >= len(study) - 1


def test_adherence_load_scale_tiers():
    from backend.planner.llm_propose import _adherence_load_scale, _day_focus_targets
    from datetime import date

    scale_hi, avg_hi = _adherence_load_scale(
        {
            "by_day": [
                {"planned_minutes": 240, "effective_focus_minutes": 200},
                {"planned_minutes": 240, "effective_focus_minutes": 210},
            ]
        }
    )
    assert scale_hi == 1.0
    assert avg_hi is not None and avg_hi >= 80

    scale_mid, _ = _adherence_load_scale(
        {
            "by_day": [
                {"planned_minutes": 240, "effective_focus_minutes": 160},
                {"planned_minutes": 240, "effective_focus_minutes": 170},
            ]
        }
    )
    assert scale_mid == 0.9

    scale_lo, _ = _adherence_load_scale(
        {
            "by_day": [
                {"planned_minutes": 240, "effective_focus_minutes": 100},
                {"planned_minutes": 240, "effective_focus_minutes": 120},
            ]
        }
    )
    assert scale_lo == 0.8

    goals = "Daily effective-focus target: 4h. Weekly target: 24h."
    full = _day_focus_targets(goals, date(2026, 7, 13), 1, load_scale=1.0)
    soft = _day_focus_targets(goals, date(2026, 7, 13), 1, load_scale=0.8)
    assert full[0] == 240
    assert soft[0] == 192


def test_carry_forward_shortfall_to_next_day():
    """Day-1 shortfall should increase day-2 study when day-2 has free gaps."""
    from datetime import datetime, timedelta

    from backend.planner.llm_propose import propose_week_from_export

    goals = "Scaler practice. Daily effective-focus target: 3h. Weekly target: 15h."
    # Busy almost all of Monday; Tuesday wide open
    routines = [
        {
            "title": "Locked Mon",
            "category": "personal",
            "start_time": "06:00",
            "end_time": "22:30",
            "days": ["mon"],
            "enabled": True,
        }
    ]
    export = {"summary": {"peak_hours": [10, 14]}, "weekday_patterns": {}, "by_day": []}
    today = date.today()
    monday = today + timedelta(days=(7 - today.weekday()) % 7)
    tuesday = monday + timedelta(days=1)
    result = propose_week_from_export(
        export,
        goals=goals,
        range_start=monday,
        horizon_days=2,
        use_llm=False,
        mode="smart",
        routines=routines,
    )
    study = [b for b in result["blocks"] if b.get("source") == "study"]

    def day_mins(d: date) -> int:
        total = 0
        for b in study:
            s = datetime.fromisoformat(b["start_at"])
            local = s.astimezone() if s.tzinfo else s
            if local.date() != d:
                continue
            e = datetime.fromisoformat(b["end_at"])
            el = e.astimezone() if e.tzinfo else e
            total += int((el - local).total_seconds() // 60)
        return total

    mon = day_mins(monday)
    tue = day_mins(tuesday)
    assert mon < 90, f"Mon should be constrained, got {mon}m"
    # Tue should absorb base 3h + carry (capped ~1.5h) → well above plain 3h
    assert tue >= 210, f"Tue should carry Mon shortfall, got {tue}m (Mon={mon}m)"
