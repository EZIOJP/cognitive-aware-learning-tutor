"""Browser telemetry endpoint + sitting parse."""

from __future__ import annotations

from datetime import date

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.db.base import Base
from backend.models.user import User
from backend.models.wearable_daily import WearableDaily
from backend.wearables.ingest_service import serialize_wearable_daily, upsert_wearable_daily


def test_normalize_and_append_telemetry(tmp_path, monkeypatch):
    from backend.behavior import browser_telemetry as bt

    monkeypatch.setattr(bt, "LOG_DIR", tmp_path)
    payload = bt.normalize_telemetry_payload(
        {
            "source": "extension",
            "browser": "edge",
            "domain_only": False,
            "active": {
                "url": "https://github.com/foo/bar?token=SECRET&x=1",
                "title": "Repo",
            },
            "tab_count": 4,
            "open_tabs": [
                {"url": "https://www.scaler.com/academy/", "title": "Scaler", "active": True},
                {"url": "chrome://newtab/", "title": "New"},
            ],
            "recent_history": [{"domain": "arxiv.org", "title": "Paper"}],
            "gate_locked": True,
            "ts": 1,
        }
    )
    assert payload["active_domain"] == "github.com"
    assert "token=" not in (payload["active_url"] or "")
    assert payload["tab_count"] == 4
    assert any(t.get("domain") == "scaler.com" for t in payload["open_tabs"])
    path = bt.append_telemetry_logs(payload, day_str="2026-08-04")
    assert path.name == "DSC_browser_telemetry_2026-08-04.jsonl"
    assert path.exists()
    assert (tmp_path / "DSC_browser_telemetry_2026-08-04.csv").exists()
    text = path.read_text(encoding="utf-8")
    assert "github.com" in text
    assert "SECRET" not in text


def test_browser_telemetry_endpoint(tmp_path, monkeypatch):
    from backend.behavior import browser_telemetry as bt
    from backend.main import app

    monkeypatch.setattr(bt, "LOG_DIR", tmp_path)
    client = TestClient(app)
    r = client.post(
        "/api/behavior/browser-telemetry",
        json={
            "browser": "chrome",
            "active": {"url": "https://docs.python.org/3/", "title": "Docs"},
            "tab_count": 2,
            "open_tabs": [
                {"url": "https://docs.python.org/3/", "domain": "docs.python.org", "active": True}
            ],
            "recent_history": [{"domain": "wikipedia.org"}],
        },
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["ok"] is True
    assert body["active_domain"] == "docs.python.org"
    assert list(tmp_path.glob("DSC_browser_telemetry_*.jsonl"))


def test_extract_sitting_minutes():
    from backend.wearables.sitting import extract_sitting_minutes, stand_summary

    assert extract_sitting_minutes({}) is None
    assert extract_sitting_minutes({"stand": {"hours": 5}}) is None
    assert extract_sitting_minutes({"activity": {"steps": 100, "sitting_min": 240}}) == 240
    assert extract_sitting_minutes({"sitting": {"minutes": 90}}) == 90
    s = stand_summary(
        {"stand": {"hours": 5, "target": 12}, "activity": {"sitting_min": 180}}
    )
    assert s["stand_hours"] == 5
    assert s["sitting_min"] == 180
    assert "Stand 5/12h" in (s["label"] or "")
    assert "Sitting" in (s["label"] or "")


def test_sitting_in_full_snapshot():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    db = Session()
    user = User(id=1, username="sit_test", password_hash="x", is_admin=True)
    db.add(user)
    db.commit()
    out = upsert_wearable_daily(
        db,
        user,
        date(2026, 8, 4),
        {
            "activity": {"steps": 1000, "sitting_min": 300},
            "stand": {"hours": 4, "target": 12},
        },
        source="mini_program",
    )
    assert out["sitting_min"] == 300
    assert out["stand_hours"] == 4
    row = (
        db.query(WearableDaily)
        .filter(WearableDaily.user_id == user.id, WearableDaily.local_date == date(2026, 8, 4))
        .one()
    )
    ser = serialize_wearable_daily(row)
    assert ser is not None
    assert ser["sitting_min"] == 300
    db.close()
