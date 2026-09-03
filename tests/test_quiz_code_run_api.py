"""POST /api/quiz/code/run grades coding submissions against test cases."""

from __future__ import annotations

from fastapi.testclient import TestClient

from backend.core.auth import get_current_user
from backend.main import app
from backend.models import User


def test_code_run_route_grades_addition():
    user = User(id=1, username="test", password_hash="hash")
    app.dependency_overrides[get_current_user] = lambda: user
    client = TestClient(app)
    try:
        r = client.post(
            "/api/quiz/code/run",
            json={
                "item": {
                    "entry_point": "add",
                    "test_cases": [
                        {"name": "t1", "input": [1, 2], "expected_output": 3},
                    ],
                },
                "code": "def add(a, b):\n    return a + b\n",
            },
        )
        assert r.status_code == 200
        body = r.json()
        assert body["all_passed"] is True
        assert body["passed"] == 1
        assert body["correct"] is True
        assert body["total"] == 1
        assert isinstance(body.get("outcomes"), list)
        assert body["outcomes"][0]["passed"] is True
    finally:
        app.dependency_overrides.pop(get_current_user, None)


def test_code_run_requires_item_or_item_id():
    user = User(id=1, username="test", password_hash="hash")
    app.dependency_overrides[get_current_user] = lambda: user
    client = TestClient(app)
    try:
        r = client.post(
            "/api/quiz/code/run",
            json={"code": "print('hi')"},
        )
        assert r.status_code == 400
        body = r.json()
        msg = str(body.get("detail") or body.get("error", {}).get("message") or "")
        assert "item" in msg.lower()
    finally:
        app.dependency_overrides.pop(get_current_user, None)
