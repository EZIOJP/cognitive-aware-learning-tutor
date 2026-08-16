"""Tests for standalone desktop tracker — bridge, checkpoint, stats aggregation."""

from __future__ import annotations

import json
import time
from datetime import UTC, datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.behavior.category_scores import seed_category_scores
from backend.behavior.tracker_classify import classify_app
from backend.behavior.session_key import session_identity
from backend.behavior.session_merge import merge_tracked_rows
from backend.behavior.tracker_service import ActiveSession
from backend.behavior.tracker_storage import SessionCheckpoint, request_tracker_flush, wait_for_flush_ack
from backend.behavior.router import _desktop_stats_from_tracked_sessions, TRACKER_ALIVE_SECONDS
from backend.db.base import Base
from backend.models.timetable import TrackedSession
from backend.models.user import User
from backend.timetable.tracker_bridge import ingest_desktop_session


@pytest.fixture()
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    user = User(id=1, username="tracker_test", password_hash="x")
    session.add(user)
    session.commit()
    seed_category_scores(session)
    yield session
    session.close()


def _session_end_payload(**overrides) -> dict:
    now = time.time()
    started = now - 120
    base = {
        "type": "SESSION_END",
        "source": "desktop_tracker",
        "exe": "Cursor.exe",
        "title": "plan.md - Cognitive-Aware Learning Tutor - Cursor",
        "category": "IDE / Code Editor",
        "productivity_score": 95,
        "duration_seconds": 120,
        "timestamp": int(started * 1000),
        "end_timestamp": int(now * 1000),
        "reason": "app_switch",
        "pid": 1234,
    }
    base.update(overrides)
    return base


def test_ingest_desktop_session_idempotent(db_session):
    payload = _session_end_payload()
    first = ingest_desktop_session(db_session, user_id=1, payload=payload)
    second = ingest_desktop_session(db_session, user_id=1, payload=payload)
    assert first is not None
    assert second is not None
    assert first.session_id == second.session_id
    count = db_session.query(TrackedSession).count()
    assert count == 1


def test_ingest_stores_window_title_and_app_name(db_session):
    payload = _session_end_payload()
    row = ingest_desktop_session(db_session, user_id=1, payload=payload)
    assert row is not None
    assert row.window_title == payload["title"]
    assert row.app_name == "Cursor.exe"
    assert row.category == "IDE / Code Editor"


def test_checkpoint_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "backend.behavior.tracker_storage.CHECKPOINT_PATH",
        tmp_path / "tracker_state.json",
    )
    cp = SessionCheckpoint(
        last_poll_at=1000.0,
        current={
            "exe": "a.exe",
            "title": "t",
            "pid": 1,
            "group_key": "a.exe",
            "site": "a.exe",
            "latest_title": "t",
            "category": "Other",
            "score": 35,
            "started_at": 999.0,
        },
    )
    cp.save()
    loaded = SessionCheckpoint.load()
    assert loaded is not None
    assert loaded.last_poll_at == 1000.0
    assert loaded.current["exe"] == "a.exe"


def test_active_session_to_event_duration():
    started = time.time() - 10
    session = ActiveSession.start("Code.exe", "test", 1)
    session.started_at = started
    ev = session.to_event("periodic_flush")
    assert ev["duration_seconds"] >= 10
    assert ev["source"] == "desktop_tracker"
    assert ev["domain"] == "Code.exe"


def test_session_identity_same_browser_site():
    k1, _ = session_identity("msedge.exe", "part 2 - YouTube - Microsoft Edge")
    k2, _ = session_identity("msedge.exe", "part 3 - YouTube and 9 more pages - Edge")
    assert k1 == k2


def test_session_identity_different_sites():
    k1, _ = session_identity("msedge.exe", "GitHub - Microsoft Edge")
    k2, _ = session_identity("msedge.exe", "YouTube - Microsoft Edge")
    assert k1 != k2


def test_session_identity_zen_browser():
    k1, site = session_identity("zen.exe", "NumPy Tutorial - YouTube — Zen Browser")
    k2, _ = session_identity("zen.exe", "Another video - YouTube — Zen Browser")
    assert k1 == k2
    assert "youtube" in site.lower()


def test_active_session_classifies_at_flush_with_latest_title():
    session = ActiveSession.start("msedge.exe", "Loading...", 1)
    session.latest_title = "Linear Algebra - Coursera - Microsoft Edge"
    ev = session.to_event("app_switch")
    assert "Coursework" in ev["category"] or ev["productivity_score"] >= 80
    assert ev["domain"] == "coursera.org"


def test_merge_adjacent_sessions(db_session):
    now = datetime.now(UTC)
    a_start = now - timedelta(minutes=10)
    a_end = now - timedelta(minutes=9, seconds=30)
    b_start = a_end + timedelta(seconds=2)
    b_end = now - timedelta(minutes=8)
    for sid, start, end in [
        ("s1", a_start, a_end),
        ("s2", b_start, b_end),
    ]:
        db_session.add(
            TrackedSession(
                session_id=sid,
                user_id=1,
                start_time=start,
                end_time=end,
                source="desktop_tracker",
                category="Video (YouTube)",
                app_name="msedge.exe",
                window_title="YouTube",
            )
        )
    db_session.commit()
    rows = db_session.query(TrackedSession).order_by(TrackedSession.start_time).all()
    merged = merge_tracked_rows(rows)
    assert len(merged) == 1
    assert (merged[0].end_time - merged[0].start_time).total_seconds() >= 110


def test_flush_request_ack(tmp_path, monkeypatch):
    monkeypatch.setattr("backend.behavior.tracker_storage.APP_DATA_DIR", tmp_path)
    monkeypatch.setattr("backend.behavior.tracker_storage.FLUSH_REQUEST_PATH", tmp_path / "tracker_flush.request")
    monkeypatch.setattr("backend.behavior.tracker_storage.FLUSH_ACK_PATH", tmp_path / "tracker_flush.ack")
    since = request_tracker_flush()
    assert (tmp_path / "tracker_flush.request").exists()
    from backend.behavior.tracker_storage import write_flush_ack

    write_flush_ack()
    assert wait_for_flush_ack(since, timeout_s=1.0)


def test_classify_study_browser():
    cat, score = classify_app("msedge.exe", "LeetCode - Two Sum - Problem")
    assert "Coursework" in cat or score >= 80


def test_desktop_stats_from_tracked_sessions(db_session):
    now = datetime.now(UTC)
    start = now - timedelta(minutes=30)
    db_session.add(
        TrackedSession(
            session_id="desktop-test1",
            user_id=1,
            start_time=start,
            end_time=now,
            source="desktop_tracker",
            category="IDE / Code Editor",
            app_name="Cursor.exe",
            window_title="main.py - Cursor",
        )
    )
    db_session.commit()

    today = now.date()
    stats = _desktop_stats_from_tracked_sessions(db_session, [1], today)
    assert stats["total_seconds"] >= 1700
    assert stats["source"] == "tracked_sessions"
    assert len(stats["sessions"]) >= 1
    assert stats["sessions"][0]["exe"] == "Cursor.exe"
    assert stats["sessions"][0]["productivity_score"] == 95


def test_desktop_stats_browser_site_split(db_session):
    now = datetime.now(UTC)
    db_session.add(
        TrackedSession(
            session_id="desktop-browser-yt",
            user_id=1,
            start_time=now - timedelta(minutes=20),
            end_time=now - timedelta(minutes=10),
            source="desktop_tracker",
            category="Browser",
            app_name="msedge.exe",
            window_title="Funny clip - YouTube - Microsoft Edge",
        )
    )
    db_session.add(
        TrackedSession(
            session_id="desktop-browser-gh",
            user_id=1,
            start_time=now - timedelta(minutes=10),
            end_time=now,
            source="desktop_tracker",
            category="Coursework (Browser)",
            app_name="msedge.exe",
            window_title="Pull requests - GitHub - Microsoft Edge",
        )
    )
    db_session.commit()

    stats = _desktop_stats_from_tracked_sessions(db_session, [1], now.date())
    browser = next((s for s in stats["sessions"] if s.get("kind") == "browser"), None)
    assert browser is not None
    assert browser["exe"] == "msedge.exe"
    assert len(browser["sites"]) >= 2
    site_names = {s["site"] for s in browser["sites"]}
    assert "youtube.com" in site_names or any("youtube" in n for n in site_names)


def test_is_ignored_move_mouse():
    from backend.behavior.tracker_ignore import is_ignored_app

    assert is_ignored_app("Move Mouse.exe", "Move Mouse")
    assert not is_ignored_app("Cursor.exe", "main.py")


def test_is_ignored_msedge_for_extension_ownership():
    """Desktop must not record Edge — SelfTracker extension owns browser sessions."""
    from backend.behavior.tracker_ignore import is_ignored_app

    assert is_ignored_app("msedge.exe", "Scaler | Dashboard")
    assert is_ignored_app("msedgewebview2.exe", "")
    assert is_ignored_app("C:\\Program Files\\Microsoft\\Edge\\Application\\msedge.exe", "YouTube")
    assert not is_ignored_app("chrome.exe", "Gmail")
    assert not is_ignored_app("firefox.exe", "Mozilla Firefox")


def test_merge_for_calendar_drops_move_mouse():
    from backend.behavior.session_merge import merge_for_calendar

    now = datetime.now(UTC)
    rows = [
        type("R", (), {
            "app_name": "Move Mouse.exe",
            "window_title": "Move Mouse",
            "category": "Other",
            "start_time": now - timedelta(hours=1),
            "end_time": now,
        })(),
        type("R", (), {
            "app_name": "Cursor.exe",
            "window_title": "app.py",
            "category": "IDE / Code Editor",
            "start_time": now - timedelta(minutes=45),
            "end_time": now - timedelta(minutes=5),
        })(),
    ]
    out = merge_for_calendar(rows)
    assert len(out) == 1
    assert out[0].app_name == "Cursor.exe"


def test_tracker_alive_threshold_constant():
    assert TRACKER_ALIVE_SECONDS == 300


def test_short_session_rejected(db_session):
    payload = _session_end_payload(duration_seconds=1)
    payload["end_timestamp"] = payload["timestamp"] + 1000
    row = ingest_desktop_session(db_session, user_id=1, payload=payload)
    assert row is None


def test_fetch_plan_context_current_and_next(db_session):
    from backend.behavior.tracker_plan import fetch_plan_context
    from backend.models.planner import PlannerBlock

    now = datetime(2026, 7, 4, 10, 0, 0, tzinfo=timezone.utc)
    db_session.add(
        PlannerBlock(
            user_id=1,
            title="Morning study",
            category="study",
            start_at=now - timedelta(hours=1),
            end_at=now + timedelta(minutes=30),
            planned_minutes=90,
            remaining_minutes=30,
            status="in_progress",
        )
    )
    db_session.add(
        PlannerBlock(
            user_id=1,
            title="Lunch",
            category="personal",
            start_at=now + timedelta(hours=2),
            end_at=now + timedelta(hours=3),
            planned_minutes=60,
            remaining_minutes=60,
            status="scheduled",
        )
    )
    db_session.commit()

    ctx = fetch_plan_context(1, now=now, db=db_session)
    assert ctx.current is not None
    assert ctx.current.title == "Morning study"
    assert ctx.current.minutes_left == 30
    assert ctx.next is not None
    assert ctx.next.title == "Lunch"


def test_fetch_plan_context_empty_day(db_session):
    from backend.behavior.tracker_plan import fetch_plan_context

    now = datetime(2026, 7, 4, 10, 0, 0, tzinfo=timezone.utc)
    ctx = fetch_plan_context(1, now=now, db=db_session)
    assert ctx.current is None
    assert ctx.next is None


def test_fetch_today_schedule_ordered(db_session):
    from backend.behavior.tracker_plan import fetch_today_schedule
    from backend.models.planner import PlannerBlock

    now = datetime(2026, 7, 4, 10, 0, 0, tzinfo=timezone.utc)
    db_session.add(
        PlannerBlock(
            user_id=1,
            title="Later block",
            category="study",
            start_at=now + timedelta(hours=2),
            end_at=now + timedelta(hours=3),
            planned_minutes=60,
            remaining_minutes=60,
            status="scheduled",
        )
    )
    db_session.add(
        PlannerBlock(
            user_id=1,
            title="Current block",
            category="study",
            start_at=now - timedelta(minutes=30),
            end_at=now + timedelta(minutes=30),
            planned_minutes=60,
            remaining_minutes=30,
            status="in_progress",
        )
    )
    db_session.commit()

    rows = fetch_today_schedule(1, now=now, db=db_session)
    assert len(rows) == 2
    assert rows[0].title == "Current block"
    assert rows[0].is_current is True
    assert rows[1].title == "Later block"


def test_tray_launcher_scripts_exist():
    from backend.behavior.tracker_launchers import RUN_APP_BAT, STUDIO_BAT

    assert RUN_APP_BAT.is_file()
    assert STUDIO_BAT.is_file()


def test_resolve_username(db_session):
    from backend.behavior.tracker_storage import resolve_username

    assert resolve_username(1, db=db_session) == "tracker_test"


def test_append_launcher_log(tmp_path, monkeypatch):
    from backend.behavior.tracker_storage import append_launcher_log, launcher_log_path

    p = tmp_path / "launcher.log"
    monkeypatch.setattr("backend.behavior.tracker_storage.launcher_log_path", lambda: p)
    append_launcher_log("test", "hello")
    text = p.read_text(encoding="utf-8")
    assert "[test]" in text
    assert "hello" in text
