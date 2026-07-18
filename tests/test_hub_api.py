from datetime import date

from fastapi.testclient import TestClient

from backend.main import app

client = TestClient(app)


def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_hub_daily_today():
    r = client.get("/api/hub/daily/today")
    assert r.status_code == 200
    data = r.json()
    assert "segments" in data
    assert isinstance(data["segments"], list)


def test_life_daily_manual_blocked_wearable_fields():
    body = {
        "sleep_hours": 7.5,
        "sleep_quality": 4,
        "exercise_minutes": 30,
        "study_minutes": 90,
    }
    day = date.today().isoformat()
    r = client.put(f"/api/life/daily/{day}", json=body)
    assert r.status_code == 403


def test_life_daily_study_minutes_ok():
    day = date.today().isoformat()
    r = client.put(f"/api/life/daily/{day}", json={"study_minutes": 90})
    assert r.status_code == 200
    assert "life_score" in r.json()
    assert r.json()["manual_edit"] is False


def test_vocab_auth_me():
    r = client.get("/api/vocab/auth/me")
    assert r.status_code == 200
    assert "username" in r.json()
