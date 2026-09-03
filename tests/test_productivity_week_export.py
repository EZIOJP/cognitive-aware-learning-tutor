"""Smoke tests for productivity week export (timetable drafting)."""

from backend.planner.week_export import (
    MAX_EXPORT_DAYS,
    export_as_csv,
    is_empty_export_day,
    omit_empty_export_days,
)


def test_export_as_csv_headers():
    payload = {
        "by_day": [
            {
                "date": "2026-07-11",
                "weekday": "sat",
                "planned_minutes": 60,
                "actual_minutes": 45,
                "productive_minutes": 30,
                "effective_focus_minutes": 20,
                "adherence_pct": 75.0,
                "by_category_minutes": {"study": 30},
                "top_apps": [{"app": "code.exe", "minutes": 30}],
                "by_hour_minutes": {str(h): (10 if h == 10 else 0) for h in range(24)},
            }
        ],
        "suggested_timetable_hints": ["Protect 10:00 blocks."],
    }
    csv_text = export_as_csv(payload)
    assert "date,weekday,planned_minutes" in csv_text
    assert "2026-07-11,sat,60" in csv_text
    assert "Protect 10:00 blocks." in csv_text


def test_is_empty_export_day_and_omit():
    empty = {
        "date": "2026-07-09",
        "session_count": 0,
        "actual_minutes": 0,
        "productive_minutes": 0,
        "planned_minutes": 0,
        "block_count": 0,
        "wearable": None,
    }
    tracked = {**empty, "date": "2026-07-10", "session_count": 1, "actual_minutes": 30.0}
    planned = {**empty, "date": "2026-07-11", "planned_minutes": 45, "block_count": 1}
    wearable = {**empty, "date": "2026-07-12", "wearable": {"steps": 1000}}

    assert is_empty_export_day(empty) is True
    assert is_empty_export_day(tracked) is False
    assert is_empty_export_day(planned) is False
    assert is_empty_export_day(wearable) is False

    kept = omit_empty_export_days([empty, tracked, planned, wearable])
    assert [d["date"] for d in kept] == ["2026-07-10", "2026-07-11", "2026-07-12"]

    csv_text = export_as_csv({"by_day": kept, "suggested_timetable_hints": []})
    assert "2026-07-09" not in csv_text
    assert "2026-07-10" in csv_text


def test_list_nonempty_export_days_marks_sessions_and_wearables():
    from datetime import date, datetime

    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from backend.db.base import Base
    from backend.models.timetable import TrackedSession
    from backend.models.user import User
    from backend.models.wearable_daily import WearableDaily
    from backend.planner.week_export import list_nonempty_export_days

    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    db = Session()
    user = User(id=1, username="presence_user", password_hash="x")
    db.add(user)
    db.commit()

    db.add(
        TrackedSession(
            session_id="presence-1",
            user_id=1,
            start_time=datetime(2026, 7, 10, 10, 0, 0),
            end_time=datetime(2026, 7, 10, 11, 0, 0),
            source="desktop_tracker",
            category="IDE / Code Editor",
            app_name="Code.exe",
            window_title="test",
        )
    )
    db.add(
        WearableDaily(
            user_id=1,
            local_date=date(2026, 7, 12),
            source="amazfit",
            steps=1200,
        )
    )
    db.commit()

    days = list_nonempty_export_days(
        db, user, start=date(2026, 7, 9), end=date(2026, 7, 12)
    )
    assert days == ["2026-07-10", "2026-07-12"]
    db.close()


def test_week_export_skips_empty_days_by_default():
    from datetime import date, datetime

    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from backend.behavior.category_scores import seed_category_scores
    from backend.db.base import Base
    from backend.models.timetable import TrackedSession
    from backend.models.user import User
    from backend.planner.week_export import build_productivity_week_export

    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    db = Session()
    user = User(id=1, username="export_skip_empty", password_hash="x")
    db.add(user)
    db.commit()
    seed_category_scores(db)

    db.add(
        TrackedSession(
            session_id="export-skip-1",
            user_id=1,
            start_time=datetime(2026, 7, 10, 10, 0, 0),
            end_time=datetime(2026, 7, 10, 11, 0, 0),
            source="desktop_tracker",
            category="IDE / Code Editor",
            app_name="Code.exe",
            window_title="test",
        )
    )
    db.commit()

    end = date(2026, 7, 12)
    payload = build_productivity_week_export(db, user, days=3, end_day=end)
    assert payload["range"]["days"] == 3
    assert payload["range"]["skip_empty"] is True
    assert payload["range"]["days_exported"] == 1
    assert payload["range"]["empty_days_omitted"] == 2
    assert [d["date"] for d in payload["by_day"]] == ["2026-07-10"]

    full = build_productivity_week_export(
        db, user, days=3, end_day=end, skip_empty=False
    )
    assert len(full["by_day"]) == 3
    assert full["range"]["empty_days_omitted"] == 0
    db.close()


def test_week_export_allows_multi_month_window():
    from datetime import date

    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from backend.behavior.category_scores import seed_category_scores
    from backend.db.base import Base
    from backend.models.user import User
    from backend.planner.week_export import build_productivity_week_export

    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    db = Session()
    user = User(id=1, username="export_long", password_hash="x")
    db.add(user)
    db.commit()
    seed_category_scores(db)

    payload = build_productivity_week_export(
        db, user, days=90, end_day=date(2026, 7, 10), skip_empty=False
    )
    assert payload["range"]["days"] == 90
    assert len(payload["by_day"]) == 90

    capped = build_productivity_week_export(
        db, user, days=9999, end_day=date(2026, 7, 10), skip_empty=False
    )
    assert capped["range"]["days"] == MAX_EXPORT_DAYS
    assert len(capped["by_day"]) == MAX_EXPORT_DAYS
    db.close()


def test_week_export_tolerates_naive_session_datetimes():
    """SQLite often returns naive datetimes; day bounds are aware — must not TypeError."""
    from datetime import date, datetime

    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from backend.behavior.category_scores import seed_category_scores
    from backend.db.base import Base
    from backend.models.timetable import TrackedSession
    from backend.models.user import User
    from backend.planner.week_export import build_productivity_week_export

    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    db = Session()
    user = User(id=1, username="export_tz", password_hash="x")
    db.add(user)
    db.commit()
    seed_category_scores(db)

    start = datetime(2026, 7, 10, 10, 0, 0)  # naive
    end = datetime(2026, 7, 10, 11, 0, 0)
    db.add(
        TrackedSession(
            session_id="export-tz-1",
            user_id=1,
            start_time=start,
            end_time=end,
            source="desktop_tracker",
            category="IDE / Code Editor",
            app_name="Code.exe",
            window_title="test",
        )
    )
    db.commit()

    payload = build_productivity_week_export(db, user, days=1, end_day=date(2026, 7, 10))
    assert payload["range"]["days"] == 1
    assert payload["by_day"][0]["session_count"] == 1
    assert payload["by_day"][0]["actual_minutes"] == 60.0
    db.close()


def test_week_export_includes_daily_wearable_metrics():
    """Watch snapshots join the matching local export day."""
    from datetime import date

    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from backend.behavior.category_scores import seed_category_scores
    from backend.db.base import Base
    from backend.models.user import User
    from backend.models.wearable_daily import WearableDaily
    from backend.planner.week_export import build_productivity_week_export, export_as_csv

    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    db = Session()
    user = User(id=1, username="export_wearable", password_hash="x")
    db.add(user)
    db.add(
        WearableDaily(
            user_id=1,
            local_date=date(2026, 7, 10),
            source="zepp",
            sleep_hours=7.5,
            sleep_score=88,
            sleep_deep_min=95,
            steps=8421,
            step_target=10000,
            calories=430,
            distance_m=6100,
            hr_last=72,
            hr_resting=58,
            spo2=97,
            stress=31,
            pai_today=18,
            stand_hours=9,
            battery_pct=64,
        )
    )
    db.commit()
    seed_category_scores(db)

    payload = build_productivity_week_export(db, user, days=1, end_day=date(2026, 7, 10))
    wearable = payload["by_day"][0]["wearable"]
    assert wearable["steps"] == 8421
    assert wearable["sleep_hours"] == 7.5
    assert wearable["heart_rate_resting"] == 58
    assert wearable["spo2_pct"] == 97
    assert "steps" in export_as_csv(payload).splitlines()[0]
    db.close()


def test_local_day_bounds_utc_spans_one_local_day():
    from datetime import date, timedelta

    from backend.planner.service import local_day_bounds_utc, local_tz

    day = date(2026, 7, 12)
    start, end = local_day_bounds_utc(day)
    assert end - start == timedelta(days=1)
    assert start.astimezone(local_tz()).date() == day
    assert end.astimezone(local_tz()).date() == date(2026, 7, 13)


def test_week_export_counts_session_on_local_calendar_day():
    """A session just after local midnight belongs to that local day, not UTC day."""
    from datetime import date, datetime, timedelta, timezone

    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from backend.behavior.category_scores import seed_category_scores
    from backend.db.base import Base
    from backend.models.timetable import TrackedSession
    from backend.models.user import User
    from backend.planner.service import local_day_bounds_utc, local_tz
    from backend.planner.week_export import build_productivity_week_export

    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    db = Session()
    user = User(id=1, username="export_local_midnight", password_hash="x")
    db.add(user)
    db.commit()
    seed_category_scores(db)

    local_day = date(2026, 7, 12)
    day_start, _ = local_day_bounds_utc(local_day)
    # 30 minutes after local midnight → still on local_day; may be previous UTC date.
    sess_start = day_start + timedelta(minutes=30)
    sess_end = sess_start + timedelta(hours=1)
    # Store as naive UTC (SQLite style)
    db.add(
        TrackedSession(
            session_id="export-local-midnight-1",
            user_id=1,
            start_time=sess_start.astimezone(timezone.utc).replace(tzinfo=None),
            end_time=sess_end.astimezone(timezone.utc).replace(tzinfo=None),
            source="desktop_tracker",
            category="IDE / Code Editor",
            app_name="Code.exe",
            window_title="test",
        )
    )
    db.commit()

    payload = build_productivity_week_export(db, user, days=1, end_day=local_day)
    assert payload["by_day"][0]["date"] == local_day.isoformat()
    assert payload["by_day"][0]["session_count"] == 1
    assert payload["by_day"][0]["actual_minutes"] == 60.0

    # Confirm this would land on a different UTC calendar day when offset != 0.
    offset = datetime.now(local_tz()).utcoffset() or timedelta(0)
    if offset.total_seconds() != 0:
        utc_day = sess_start.astimezone(timezone.utc).date()
        assert utc_day != local_day or offset.total_seconds() == 0

    db.close()


def test_week_export_respects_explicit_end_day_window():
    from datetime import date

    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from backend.behavior.category_scores import seed_category_scores
    from backend.db.base import Base
    from backend.models.user import User
    from backend.planner.week_export import build_productivity_week_export

    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    db = Session()
    user = User(id=1, username="export_end_day", password_hash="x")
    db.add(user)
    db.commit()
    seed_category_scores(db)

    end = date(2026, 3, 15)
    payload = build_productivity_week_export(
        db, user, days=107, end_day=end, skip_empty=False
    )
    assert payload["range"]["days"] == 107
    assert payload["range"]["end"] == "2026-03-15"
    assert payload["range"]["start"] == "2025-11-29"
    assert len(payload["by_day"]) == 107
    db.close()


def test_export_api_accepts_long_window_and_end_day():
    """Regression: UI allows up to 366 days; old API le=31 caused 422."""
    from fastapi.testclient import TestClient

    from backend.core.auth import get_current_user
    from backend.main import app
    from backend.models import User

    user = User(id=1, username="export_api", password_hash="x")
    app.dependency_overrides[get_current_user] = lambda: user
    client = TestClient(app)
    try:
        ok = client.get(
            "/api/planner/export/last-7-days",
            params={
                "days": 107,
                "format": "json",
                "skip_empty": "true",
                "end_day": "2026-03-15",
                "include": "summary,by_day",
            },
        )
        assert ok.status_code == 200, ok.text
        body = ok.json()
        assert body["range"]["days"] == 107
        assert body["range"]["end"] == "2026-03-15"

        bad = client.get(
            "/api/planner/export/last-7-days",
            params={"days": 999, "format": "json"},
        )
        assert bad.status_code == 422
        err = bad.json()
        assert err.get("error", {}).get("code") == "validation_error"
        details = err.get("error", {}).get("details") or []
        assert any("days" in str(d.get("loc", [])) for d in details)
    finally:
        app.dependency_overrides.pop(get_current_user, None)
