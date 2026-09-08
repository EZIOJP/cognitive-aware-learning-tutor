"""Edge counts as Edge; extension sessions carry active tab fields."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from backend.behavior.browser_labels import browser_display_name
from backend.behavior.stats_aggregate import aggregate_session_rows, desktop_sessions_payload
from backend.timetable.tracker_bridge import ingest_behavior_session


def test_browser_display_edge():
    assert browser_display_name("msedge.exe") == "Microsoft Edge"
    assert browser_display_name("MSEdge.EXE") == "Microsoft Edge"


def test_extension_session_stores_edge_exe(db_session_factory=None):
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from backend.db.base import Base
    from backend.models.productivity_policy import ProductivityPolicy
    from backend.models.timetable import TrackedSession
    from backend.models.user import User

    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(
        engine, tables=[User.__table__, TrackedSession.__table__, ProductivityPolicy.__table__]
    )
    Session = sessionmaker(bind=engine)
    db = Session()
    u = User(username="edge_tab", password_hash="x")
    db.add(u)
    db.commit()
    uid = int(u.id)
    now = datetime.now(timezone.utc)
    start_ms = int((now - timedelta(seconds=30)).timestamp() * 1000)
    end_ms = int(now.timestamp() * 1000)
    row = ingest_behavior_session(
        db,
        user_id=uid,
        payload={
            "type": "SESSION_END",
            "source": "extension",
            "exe": "msedge.exe",
            "browser": "Edge",
            "domain": "youtube.com",
            "url": "https://www.youtube.com/watch?v=abc",
            "title": "Some Video",
            "tab_id": 42,
            "duration_seconds": 30,
            "timestamp": start_ms,
            "end_timestamp": end_ms,
            "category": "Video / Streaming",
            "active_tab_only": True,
        },
    )
    assert row is not None
    assert row.app_name == "msedge.exe"
    assert "youtube.com" in (row.window_title or "")
    assert "Some Video" in (row.window_title or "")

    buckets, total = aggregate_session_rows([row], scores={})
    assert total >= 30
    assert "msedge.exe" in buckets
    assert "Browser (Web)" not in buckets
    assert "youtube.com" in buckets["msedge.exe"].sites
    payload = desktop_sessions_payload(buckets)
    assert payload[0]["display_name"] == "Microsoft Edge"
    assert payload[0]["exe"] == "msedge.exe"
    assert payload[0]["kind"] == "browser"
    db.close()
