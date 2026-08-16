"""Smoke tests for productivity week export (timetable drafting)."""

from backend.planner.week_export import export_as_csv


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
