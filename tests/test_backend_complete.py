from datetime import date

from fastapi.testclient import TestClient

from backend.main import app

client = TestClient(app)


def test_health_includes_schema():
    r = client.get("/health")
    assert r.status_code == 200
    data = r.json()
    assert "schema_revision" in data
    assert "schema_ok" in data


def test_behavior_stats_shape():
    r = client.get("/api/behavior/stats")
    assert r.status_code == 200
    data = r.json()
    assert "events_today" in data
    assert "domains" in data
    assert data.get("source") in ("database", "csv_fallback")


def test_account_export_json():
    r = client.get("/api/account/export")
    assert r.status_code == 200
    data = r.json()
    assert data["export_version"] == "1.0"
    assert "user" in data
    assert "word_progress" in data


def test_quiz_start_returns_hub_session():
    r = client.post(
        "/api/vocab/quiz/adaptive/start/",
        json={"quiz_type": "adaptive_group", "group_number": 1},
    )
    assert r.status_code == 200
    body = r.json()
    assert "session_id" in body
    assert "hub_session_id" in body
    assert body["hub_session_id"] is not None


def test_validation_error_envelope():
    r = client.put(f"/api/life/daily/{date.today().isoformat()}", json={})
    assert r.status_code in (200, 422)
    if r.status_code == 422:
        data = r.json()
        assert "error" in data
        assert data["error"]["code"] == "validation_error"
