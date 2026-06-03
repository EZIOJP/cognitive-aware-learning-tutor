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


def test_life_daily_upsert():
    body = {
        "sleep_hours": 7.5,
        "sleep_quality": 4,
        "exercise_minutes": 30,
        "water_glasses": 8,
        "meals_healthy": 3,
        "study_minutes": 90,
        "tasks_completed": 2,
        "deep_work_blocks": 1,
        "screen_time_hours": 3,
        "social_media_minutes": 45,
        "outdoor_minutes": 20,
        "mood_score": 4,
        "stress_level": 2,
        "meditation_minutes": 10,
    }
    day = date.today().isoformat()
    r = client.put(f"/api/life/daily/{day}", json=body)
    assert r.status_code == 200
    assert "life_score" in r.json()
    assert r.json()["life_score"] > 0


def test_vocab_auth_me():
    r = client.get("/api/vocab/auth/me")
    assert r.status_code == 200
    assert "username" in r.json()
