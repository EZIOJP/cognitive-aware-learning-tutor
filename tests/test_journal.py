"""Tests for daily journal API."""

from fastapi.testclient import TestClient

from backend.main import app

client = TestClient(app)


def test_journal_summary():
    res = client.get("/api/journal/summary")
    assert res.status_code == 200
    data = res.json()
    assert "day" in data
    assert "journal_written" in data


def test_journal_roundtrip():
    journal = client.post(
        "/api/journal/entries",
        json={"title": "Evening", "content": "Grateful for a productive day."},
    )
    assert journal.status_code == 200
    assert journal.json()["entry"]["content"].startswith("Grateful")

    summary = client.get("/api/journal/summary").json()
    assert summary["journal_written"] is True


def test_journal_upsert_updates_same_day():
    first = client.post("/api/journal/entries", json={"content": "First draft for upsert test."})
    assert first.status_code == 200

    second = client.post(
        "/api/journal/entries",
        json={"content": "Updated thoughts for upsert test.", "title": "Today"},
    )
    assert second.status_code == 200
    body = second.json()
    assert body["created"] is False
    assert body["entry"]["content"] == "Updated thoughts for upsert test."
