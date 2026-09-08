"""Tests for day coach, sleep anchor, voice day commands."""

from __future__ import annotations

from datetime import date

import pytest


def test_sleep_target_eight_hours_from_six_am() -> None:
    from backend.behavior.calt_desktop.sleep_anchor import sleep_target_hm

    assert sleep_target_hm("06:00", sleep_hours=8) == (22, 0)


def test_day_end_before_sleep() -> None:
    from backend.behavior.calt_desktop.sleep_anchor import day_end_minutes

    end = day_end_minutes("06:00", sleep_hours=8)
    assert end == 21 * 60 + 30


def test_voice_apply_my_day_phrase(monkeypatch: pytest.MonkeyPatch) -> None:
    from backend.behavior.calt_desktop import voice_day_commands as vdc

    calls: list[int] = []

    def fake_apply(uid: int, **kwargs):
        calls.append(uid)
        return {"ok": True, "routines_created": 1, "study_created": 2}

    monkeypatch.setattr(
        "backend.behavior.calt_desktop.day_coach.apply_my_day",
        fake_apply,
    )
    out = vdc.try_day_command(1, "apply my day")
    assert out is not None
    assert "1" in out and "2" in out
    assert calls == [1]


def test_current_week_key_format() -> None:
    from backend.behavior.calt_desktop.day_coach import current_week_key

    wk = current_week_key(date(2026, 9, 1))
    assert wk.startswith("2026-W")


def test_gate_profile_study() -> None:
    from backend.behavior.calt_desktop.block_gate import gate_profile_for_block

    p = gate_profile_for_block({"title": "Scaler block", "category": "study"})
    assert p["mode"] == "study"


def test_apply_my_day_accepts_goals_override(monkeypatch: pytest.MonkeyPatch) -> None:
    from backend.behavior.calt_desktop import day_coach as dc

    captured: dict = {}

    def fake_run_propose_merged(uid, **kwargs):
        captured["goals"] = kwargs.get("goals")
        return {"blocks": []}

    monkeypatch.setattr(dc, "reorder_morning_routines", lambda uid: None)
    monkeypatch.setattr(dc, "apply_routines_today", lambda uid: {"created": 0})
    monkeypatch.setattr(dc, "run_propose_merged", fake_run_propose_merged)
    monkeypatch.setattr(dc, "materialize_study_task_blocks", lambda *a, **k: [])
    monkeypatch.setattr(dc, "apply_proposed_filtered", lambda *a, **k: {"created": 0})
    monkeypatch.setattr(
        "backend.behavior.calt_desktop.apply_snapshot.save_before_apply",
        lambda *a, **k: 0,
    )
    monkeypatch.setattr(dc, "blocks_for_day", lambda *a, **k: [])

    res = dc.apply_my_day(1, goals_prompt="Web goals text", study_tasks=[], snapshot=False)
    assert res["ok"] is True
    assert captured.get("goals") == "Web goals text"


def test_apply_day_rhythm_route_shape() -> None:
    from backend.planner.morning_order import apply_day_rhythm, morning_order_rule_text

    blocks = [
        {
            "title": "Study",
            "category": "study",
            "start_at": "2026-09-02T08:00:00+05:30",
            "end_at": "2026-09-02T09:00:00+05:30",
            "source": "study",
        }
    ]
    out = apply_day_rhythm(blocks, day=date(2026, 9, 2))
    assert len(out) >= 1
    rule = morning_order_rule_text(day=date(2026, 9, 2))
    assert "routines" in rule.lower()
