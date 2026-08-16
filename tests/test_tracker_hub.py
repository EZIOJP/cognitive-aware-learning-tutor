"""Tracker LAN hub — health + auth + gate route."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient


def test_hub_health_and_unauthorized_gate():
    from backend.behavior.tracker_hub import _build_app, hub_port

    app = _build_app()
    client = TestClient(app)

    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert body["service"] == "calt.tracker_hub"
    assert body["port"] == hub_port()

    denied = client.get("/api/hub/gate")
    assert denied.status_code == 401


def test_hub_gate_returns_progress():
    from backend.db.session import get_db
    from backend.wearables.router import require_wearable_key

    fake_user = MagicMock()
    fake_user.id = 1
    gate = {
        "enabled": True,
        "locked": True,
        "unlocked": False,
        "productive_minutes": 10,
        "daily_goal_minutes": 240,
        "remaining_minutes": 230,
        "hard_block_gaming": True,
    }

    with (
        patch(
            "backend.behavior.distraction_gate.compute_distraction_gate",
            return_value=gate,
        ),
        patch("backend.core.auth.ensure_solo_owner", return_value=fake_user),
    ):
        from backend.behavior.tracker_hub import _build_app

        app = _build_app()

        def _db():
            yield MagicMock()

        app.dependency_overrides[get_db] = _db
        app.dependency_overrides[require_wearable_key] = lambda: None
        client = TestClient(app)
        r = client.get("/api/hub/gate")
        assert r.status_code == 200
        data = r.json()
        assert data["ok"] is True
        assert data["locked"] is True
        assert data["productive_minutes"] == 10
        assert data["remaining_minutes"] == 230
