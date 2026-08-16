"""PC-on during sleep must not count toward productive minutes."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.behavior.category_scores import seed_category_scores
from backend.behavior.distraction_gate import compute_distraction_gate
from backend.db.base import Base
from backend.models.timetable import TrackedSession
from backend.models.user import User
from backend.models.wearable_daily import WearableDaily
from backend.planner.service import local_tz


def _db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    db = Session()
    db.add(User(id=1, username="sleep_null", password_hash="x"))
    db.commit()
    seed_category_scores(db)
    return db


def test_productive_minutes_exclude_sleep_overlap(monkeypatch, tmp_path):
    from backend.planner import morning_rewards as mr

    monkeypatch.setattr(mr, "_STORE", tmp_path / "morning_rewards.json")
    monkeypatch.setattr(
        "backend.behavior.productivity_policy.load_policy_dict",
        lambda db, uid: {
            "hard_block_enabled": True,
            "daily_goal_minutes": 240,
            "threshold": 60,
            "hard_block_gaming": True,
            "hard_block_exes": [],
            "productive_categories": ["IDE / Code Editor"],
            "blocked_categories": [],
            "app_overrides": {},
        },
    )
    monkeypatch.setattr(
        "backend.behavior.productivity_policy.resolve_session_score",
        lambda sess, scores, policy: 90,
    )
    monkeypatch.setattr(
        "backend.bible.store.summary",
        lambda uid: {
            "bible_minutes": 0,
            "game_bank_remaining_seconds": 0,
            "game_bank_remaining_minutes": 0,
            "day_pass": False,
            "chapter_goal": {"met": True, "target": 1, "completed": 1},
            "chapters_completed_today": ["John 1"],
            "day_pass_status": {"used": 0, "limit": 2, "remaining": 2},
        },
    )
    monkeypatch.setattr("backend.planner.morning_plan.count_blocks_today", lambda *a, **k: 1)
    monkeypatch.setattr("backend.planner.morning_plan.is_plan_confirmed", lambda *a, **k: True)

    db = _db()
    tz = local_tz()
    today = datetime.now(tz).date()
    # Sleep 01:00–05:00 local today
    payload = json.dumps(
        {
            "sleep": {
                "start_min": 60,
                "end_min": 300,
                "total_min": 240,
                "naps": [],
            }
        }
    )
    db.add(
        WearableDaily(
            user_id=1,
            local_date=today,
            sleep_hours=4.0,
            sleep_score=70,
            payload_json=payload,
        )
    )
    # Tracker "productive" 00:00–06:00 local → only 00–01 and 05–06 should count (120m)
    day0 = datetime.combine(today, datetime.min.time(), tzinfo=tz)
    db.add(
        TrackedSession(
            session_id="pc-during-sleep",
            user_id=1,
            start_time=day0.astimezone(UTC),
            end_time=(day0 + timedelta(hours=6)).astimezone(UTC),
            source="desktop_tracker",
            category="IDE / Code Editor",
            app_name="code.exe",
            window_title="work",
            category_source="test",
        )
    )
    db.commit()

    gate = compute_distraction_gate(db, 1)
    assert gate["productive_minutes"] == 120, gate["productive_minutes"]
