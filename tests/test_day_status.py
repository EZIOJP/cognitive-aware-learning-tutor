"""Unit tests for day-status aggregation (mobile / Amazfit bridge)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from backend.behavior.day_status import (
    build_checklist,
    build_day_status,
    drain_mobile_alerts,
    peek_mobile_alerts,
    _notify_payload,
)


def test_notify_payload_bible_first():
    n = _notify_payload(
        browser_mode="bible",
        morning_next="bible",
        hard_block_armed=True,
        locked=True,
    )
    assert n["title"] == "Bible first"
    assert "chapter" in n["body"].lower()


def test_notify_payload_study_mode():
    n = _notify_payload(
        browser_mode="study",
        morning_next="open",
        hard_block_armed=True,
        locked=False,
    )
    assert n["title"] == "Study mode"
    assert n["browser_mode"] == "study"


def test_checklist_active_steps():
    morning = {
        "bible_done": True,
        "plan_done": False,
        "plan_confirmed": False,
        "next": "plan",
        "bible_url": "/bible",
        "plan_url": "/productivity?tab=plan",
    }
    items = build_checklist(morning)
    by_id = {i["id"]: i for i in items}
    assert by_id["bible"]["done"] is True
    assert by_id["plan"]["active"] is True
    assert by_id["open"]["done"] is False


def test_build_day_status_aggregates(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "backend.behavior.day_status._NOTIFY_STATE_PATH",
        tmp_path / "notify.json",
    )
    monkeypatch.setattr(
        "backend.behavior.day_status._PENDING_MOBILE_PATH",
        tmp_path / "pending.json",
    )
    monkeypatch.setattr(
        "backend.behavior.day_status.ROOT",
        tmp_path,
    )
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "wearables_last_sync.json").write_text(
        '{"last_ingest_at":"2026-08-04T10:00:00Z","last_steps":100,"last_stand":4,"last_sitting_min":30}',
        encoding="utf-8",
    )

    gate = {
        "enabled": True,
        "locked": True,
        "unlocked": False,
        "productive_minutes": 40,
        "daily_goal_minutes": 240,
        "remaining_minutes": 200,
        "day_unlimited": False,
        "day": "2026-08-04",
        "browser_mode": "study",
        "browser": {"mode": "study"},
        "morning": {
            "enabled": True,
            "next": "open",
            "bible_done": True,
            "plan_done": True,
            "plan_confirmed": True,
            "blocks_today": 3,
            "hint": "Day open",
            "bible_url": "/bible",
            "plan_url": "/productivity?tab=plan",
            "suggested_wake": {"suggested_local": "2026-08-04T06:30:00", "writable_alarm": False},
        },
    }

    db = MagicMock()
    productivity_stub = {
        "date": "2026-08-04",
        "pulse": 55,
        "pulse_label": "Neutral",
        "goal_pct": 17,
        "goal_met": False,
        "focus_quality": {"score": 80, "label": "Deep focus", "switches": 2},
        "weekly": {"avg_pulse": 60, "goal_met_days": 3},
        "study_mode_nudge": {"active": False, "until": None},
    }
    with (
        patch("backend.behavior.distraction_gate.compute_distraction_gate", return_value=gate),
        patch(
            "backend.behavior.day_status._tracker_compact",
            return_value={"alive": True, "status": "running", "sessions_today": 2},
        ),
        patch(
            "backend.behavior.day_productivity.build_productivity_snapshot",
            return_value=productivity_stub,
        ),
    ):
        out = build_day_status(db, user_id=1, enqueue_notify=True)

    assert out["ok"] is True
    assert out["browser_mode"] == "study"
    assert out["browser_mode_label"] == "Study mode"
    assert out["hard_block"]["armed"] is True
    assert out["hard_block"]["locked"] is True
    assert out["tracker_alive"] is True
    assert out["wearables"]["steps"] == 100
    assert out["wearables"]["sitting_min"] == 30
    assert out["wearables"]["sitting_label"] == "0 hours 30 mins"
    assert out["hard_block"]["productive_label"] == "0 hours 40 mins"
    assert out["hard_block"]["daily_goal_label"] == "4 hours"
    assert out["schema"] == 3
    assert "productivity" in out
    assert "comms" in out
    assert "pulse" in out["productivity"]
    assert "goal_pct" in out["productivity"]
    assert out["morning"]["suggested_wake"]["writable_alarm"] is False
    assert out["alert_enqueued"] is True
    assert "limits" in out

    # Second call same fingerprint → no new enqueue
    with (
        patch("backend.behavior.distraction_gate.compute_distraction_gate", return_value=gate),
        patch(
            "backend.behavior.day_status._tracker_compact",
            return_value={"alive": True, "status": "running"},
        ),
        patch(
            "backend.behavior.day_productivity.build_productivity_snapshot",
            return_value=productivity_stub,
        ),
    ):
        out2 = build_day_status(db, user_id=1, enqueue_notify=True)
    assert out2["alert_enqueued"] is False

    pending = peek_mobile_alerts()
    assert len(pending) >= 1
    drained = drain_mobile_alerts()
    assert len(drained) >= 1
    assert peek_mobile_alerts() == []
