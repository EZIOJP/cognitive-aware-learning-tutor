"""Health Connect / bridge export → wearable ingest mapping."""

from datetime import date

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.db.base import Base
from backend.models.user import User
from backend.models.wearable_daily import WearableDaily
from backend.wearables.health_connect_map import (
    coerce_ingest_body,
    inventory_categories,
    normalize_health_connect_records,
)
from backend.wearables.ingest_service import upsert_wearable_daily


@pytest.fixture()
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    session.add(User(id=1, username="hc_user", password_hash="x", is_admin=True))
    session.commit()
    yield session
    session.close()


def test_normalize_health_connect_records_basic():
    body = normalize_health_connect_records(
        [
            {"type": "Steps", "count": 4200, "local_date": "2026-09-06"},
            {"type": "SleepSession", "duration_min": 390, "score": 78},
            {"type": "HeartRate", "bpm": 71},
            {"type": "RestingHeartRate", "bpm": 56},
            {"type": "OxygenSaturation", "percentage": 98},
            {"type": "HrvRmssd", "rmssd_ms": 42.5},
            {"type": "ExerciseSession", "title": "Run", "duration_min": 32, "calories": 280},
        ],
        local_date="2026-09-06",
    )
    assert body["source"] == "health_connect"
    assert body["activity"]["steps"] == 4200
    assert body["sleep"]["total_min"] == 390
    assert body["sleep"]["score"] == 78
    assert body["heart"]["last"] == 71
    assert body["heart"]["resting"] == 56
    assert body["spo2"]["value"] == 98
    assert body["hrv"]["rmssd_ms"] == 42.5
    assert len(body["workouts"]) == 1
    inv = inventory_categories(body)
    assert "sleep" in inv["present"]
    assert "hrv" in inv["present"]
    assert "workouts" in inv["present"]


def test_coerce_bridge_export_daily():
    out = coerce_ingest_body(
        {
            "source": "bridge_export",
            "local_date": "2026-09-05",
            "daily": {
                "steps": 8000,
                "resting_hr": 55,
                "spo2": 97,
                "stress": 33,
                "pai": 11.2,
                "hrv": 40,
                "vo2max": 48.1,
            },
            "workouts": [{"type": "walk", "duration_min": 20}],
        }
    )
    assert out["activity"]["steps"] == 8000
    assert out["heart"]["resting"] == 55
    assert out["hrv"]["rmssd_ms"] == 40
    assert out["vo2max"]["ml_kg_min"] == 48.1
    assert out["workouts"]


def test_health_connect_upsert_writes_life(db_session):
    user = db_session.query(User).first()
    mapped = normalize_health_connect_records(
        [
            {"type": "Steps", "count": 5000, "local_date": "2026-09-06"},
            {"type": "SleepSession", "duration_min": 400, "score": 80},
            {"type": "HrvRmssd", "rmssd_ms": 38},
        ]
    )
    out = upsert_wearable_daily(
        db_session,
        user,
        date(2026, 9, 6),
        mapped,
        source="health_connect",
    )
    assert out["upserted"] is True
    assert out["steps"] == 5000
    row = (
        db_session.query(WearableDaily)
        .filter(WearableDaily.user_id == user.id, WearableDaily.local_date == date(2026, 9, 6))
        .one()
    )
    assert row.source == "health_connect"
    import json

    payload = json.loads(row.payload_json)
    assert payload.get("hrv", {}).get("rmssd_ms") == 38
    assert "hrv" in inventory_categories(payload)["present"]
