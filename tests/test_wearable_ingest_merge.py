"""Wearable ingest must land in central DB without wiping sleep on partial syncs."""

from datetime import date

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.core.auth import ensure_solo_owner
from backend.db.base import Base
from backend.db.session import SessionLocal
from backend.models import LifeDailyLog, Reading
from backend.models.hub import ReadingDefinition
from backend.models.user import User
from backend.models.wearable_daily import WearableDaily, WearableIngestEvent
from backend.wearables.ingest_service import PayloadTooLarge, upsert_wearable_daily


def test_partial_sync_does_not_wipe_sleep(monkeypatch):
    db = SessionLocal()
    try:
        owner = ensure_solo_owner(db)
        day = date(2026, 7, 25)

        db.query(WearableIngestEvent).filter(WearableIngestEvent.user_id == owner.id).delete()
        db.query(WearableDaily).filter(
            WearableDaily.user_id == owner.id, WearableDaily.local_date == day
        ).delete()
        db.query(LifeDailyLog).filter(
            LifeDailyLog.user_id == owner.id, LifeDailyLog.date == day
        ).delete()
        db.commit()

        monkeypatch.setattr(
            "backend.wearables.ingest_service.rebuild_daily_rollup",
            lambda *a, **k: None,
        )

        upsert_wearable_daily(
            db,
            owner,
            day,
            {
                "sleep": {
                    "total_min": 420,
                    "score": 80,
                    "deep_min": 90,
                    "start_min": 1380,
                    "end_min": 1800,
                }
            },
            source="mini_program",
        )
        row = (
            db.query(WearableDaily)
            .filter(WearableDaily.user_id == owner.id, WearableDaily.local_date == day)
            .first()
        )
        assert row is not None
        assert float(row.sleep_hours) == 7.0

        out = upsert_wearable_daily(
            db,
            owner,
            day,
            {"activity": {"steps": 5000}, "sleep": {"total_min": 0, "score": 0, "end_min": -1}},
            source="mini_program",
        )
        db.refresh(row)
        assert float(row.sleep_hours) == 7.0
        assert out["sleep_hours"] == 7.0
        assert row.steps == 5000
        payload = __import__("json").loads(row.payload_json or "{}")
        assert payload.get("sleep", {}).get("total_min") == 420
    finally:
        db.close()


def test_chunked_ingest_merges_stand_and_battery(monkeypatch):
    db = SessionLocal()
    try:
        owner = ensure_solo_owner(db)
        day = date(2026, 8, 13)

        db.query(WearableIngestEvent).filter(WearableIngestEvent.user_id == owner.id).delete()
        db.query(WearableDaily).filter(
            WearableDaily.user_id == owner.id, WearableDaily.local_date == day
        ).delete()
        db.query(LifeDailyLog).filter(
            LifeDailyLog.user_id == owner.id, LifeDailyLog.date == day
        ).delete()
        db.commit()

        monkeypatch.setattr(
            "backend.wearables.ingest_service.rebuild_daily_rollup",
            lambda *a, **k: None,
        )

        upsert_wearable_daily(
            db,
            owner,
            day,
            {"sleep": {"total_min": 480, "score": 78, "deep_min": 90}},
            source="mini_program",
        )
        upsert_wearable_daily(
            db,
            owner,
            day,
            {
                "activity": {"steps": 1200},
                "stand": {"hours": 8, "target": 12},
                "battery": {"pct": 41},
            },
            source="mini_program",
        )
        row = (
            db.query(WearableDaily)
            .filter(WearableDaily.user_id == owner.id, WearableDaily.local_date == day)
            .first()
        )
        assert row is not None
        assert float(row.sleep_hours) == 8.0
        assert row.stand_hours == 8
        assert row.battery_pct == 41
        payload = __import__("json").loads(row.payload_json or "{}")
        assert payload.get("sleep", {}).get("total_min") == 480
        assert payload.get("stand", {}).get("hours") == 8
    finally:
        db.close()


@pytest.fixture()
def mem_db(monkeypatch):
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    user = User(id=1, username="replay_user", password_hash="x", is_admin=True)
    session.add(user)
    for slug in (
        "sleep_hours",
        "steps",
        "calories",
        "heart_rate",
        "spo2",
        "stress",
        "pai",
        "distance_m",
        "fat_burn_min",
        "hr_resting",
        "stand_hours",
    ):
        session.add(
            ReadingDefinition(
                slug=slug,
                label=slug,
                unit="n",
                source_type="device",
            )
        )
    session.commit()
    monkeypatch.setattr(
        "backend.wearables.ingest_service.rebuild_daily_rollup",
        lambda *a, **k: None,
    )
    yield session, user
    session.close()


def test_duplicate_chunk_is_noop(mem_db):
    db, user = mem_db
    day = date(2026, 8, 14)
    body = {
        "sleep": {"total_min": 400, "score": 70},
        "activity": {"steps": 3000},
        "captured_at": "2026-08-14T10:00:00+00:00",
        "meta": {
            "dump_id": "dump_2026-08-14_a",
            "chunk_id": "dump_2026-08-14_a_1",
            "checksum": "habc",
            "manual_dump": True,
        },
    }
    first = upsert_wearable_daily(db, user, day, body, source="mini_program")
    second = upsert_wearable_daily(db, user, day, body, source="mini_program")
    assert first["upserted"] is True
    assert second["duplicate"] is True
    assert second["replayed"] is True
    assert (
        db.query(WearableDaily)
        .filter(WearableDaily.user_id == user.id, WearableDaily.local_date == day)
        .count()
        == 1
    )
    assert (
        db.query(LifeDailyLog)
        .filter(LifeDailyLog.user_id == user.id, LifeDailyLog.date == day)
        .count()
        == 1
    )
    assert (
        db.query(WearableIngestEvent)
        .filter(WearableIngestEvent.user_id == user.id)
        .count()
        == 1
    )
    steps_readings = (
        db.query(Reading)
        .join(ReadingDefinition)
        .filter(Reading.user_id == user.id, ReadingDefinition.slug == "steps")
        .count()
    )
    assert steps_readings == 1


def test_out_of_order_chunks_same_final(mem_db):
    db, user = mem_db
    day = date(2026, 8, 15)
    activity = {
        "activity": {"steps": 9000},
        "calorie": {"kcal": 400},
        "captured_at": "2026-08-15T12:00:00+00:00",
        "meta": {"dump_id": "d1", "chunk_id": "d1_2", "checksum": "h2"},
    }
    sleep = {
        "sleep": {"total_min": 450, "score": 88, "stages": [{"t": 1}, {"t": 2}]},
        "captured_at": "2026-08-15T12:00:00+00:00",
        "meta": {"dump_id": "d1", "chunk_id": "d1_1", "checksum": "h1"},
    }
    upsert_wearable_daily(db, user, day, activity, source="mini_program")
    upsert_wearable_daily(db, user, day, sleep, source="mini_program")
    row = (
        db.query(WearableDaily)
        .filter(WearableDaily.user_id == user.id, WearableDaily.local_date == day)
        .one()
    )
    assert row.steps == 9000
    assert float(row.sleep_hours) == 7.5
    payload = __import__("json").loads(row.payload_json or "{}")
    assert payload["sleep"]["total_min"] == 450
    assert len(payload["sleep"]["stages"]) == 2


def test_stale_lower_activity_does_not_regress(mem_db):
    db, user = mem_db
    day = date(2026, 8, 16)
    upsert_wearable_daily(
        db,
        user,
        day,
        {
            "activity": {"steps": 10000},
            "calorie": {"kcal": 500},
            "distance": {"meters": 8000},
            "stand": {"hours": 10},
            "captured_at": "2026-08-16T18:00:00+00:00",
            "meta": {"dump_id": "fresh", "chunk_id": "fresh_1"},
        },
        source="mini_program",
    )
    upsert_wearable_daily(
        db,
        user,
        day,
        {
            "activity": {"steps": 2000},
            "calorie": {"kcal": 100},
            "distance": {"meters": 500},
            "stand": {"hours": 2},
            "captured_at": "2026-08-16T08:00:00+00:00",
            "meta": {"dump_id": "stale", "chunk_id": "stale_1"},
        },
        source="mini_program",
    )
    row = (
        db.query(WearableDaily)
        .filter(WearableDaily.user_id == user.id, WearableDaily.local_date == day)
        .one()
    )
    assert row.steps == 10000
    assert row.calories == 500
    assert row.distance_m == 8000
    assert row.stand_hours == 10


def test_reject_oversize_payload(mem_db):
    db, user = mem_db
    day = date(2026, 8, 17)
    huge = {"x": "y" * 210_000, "meta": {"chunk_id": "big_1"}}
    with pytest.raises(PayloadTooLarge):
        upsert_wearable_daily(db, user, day, huge, source="mini_program")


def test_unavailable_sensor_not_fabricated(mem_db):
    db, user = mem_db
    day = date(2026, 8, 18)
    upsert_wearable_daily(
        db,
        user,
        day,
        {
            "activity": {"steps": 100},
            "capabilities": {"temperature": False, "spo2": True},
            "meta": {"chunk_id": "cap_1"},
        },
        source="mini_program",
    )
    row = (
        db.query(WearableDaily)
        .filter(WearableDaily.user_id == user.id, WearableDaily.local_date == day)
        .one()
    )
    payload = __import__("json").loads(row.payload_json or "{}")
    assert "temperature" not in payload or payload.get("temperature") in (None, {})
    assert payload.get("capabilities", {}).get("temperature") is False
