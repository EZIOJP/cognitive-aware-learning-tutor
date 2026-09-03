"""Authored content bank is reachable from /api/quiz and quiz start."""

from __future__ import annotations

from backend.quiz import content_bank as cb


def test_content_catalog_loads_math_packs():
    catalog = cb.load_catalog(refresh=True)
    d = catalog.to_dict()
    assert d["question_count"] >= 2000
    assert d["topic_count"] >= 40
    assert not d["errors"]
    assert catalog.by_id("math.aptitude.gen-time-work")


def test_build_quiz_items_by_note_topic():
    items = cb.build_quiz_items(kind="math", note_topic_id="MT1-T07", count=3, shuffle=True)
    assert len(items) == 3
    assert all(i.get("kind") == "math" for i in items)
    assert all(i.get("expected_answer") for i in items)


def test_content_catalog_route(monkeypatch):
    from fastapi.testclient import TestClient

    from backend.core.auth import get_current_user
    from backend.main import app
    from backend.models import User

    user = User(id=1, username="test", password_hash="hash")

    def _user():
        return user

    app.dependency_overrides[get_current_user] = _user
    try:
        client = TestClient(app)
        r = client.get("/api/quiz/content/catalog?kind=math")
        assert r.status_code == 200
        body = r.json()
        assert body["question_count"] >= 2000
        assert any(t["topic_id"] == "math.aptitude.gen-time-work" for t in body["topics"])
        r2 = client.get("/api/quiz/content/curriculum")
        assert r2.status_code == 200
        assert r2.json()["levels"]
    finally:
        app.dependency_overrides.pop(get_current_user, None)
