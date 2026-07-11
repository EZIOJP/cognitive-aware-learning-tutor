"""Tests for bulk route-profile chain probing (async Huey jobs)."""

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from backend.core.auth import get_current_user
from backend.main import app
from backend.models import User


@pytest.fixture
def client():
    def override_get_current_user():
        return User(id=1, username="test", password_hash="hash")

    app.dependency_overrides[get_current_user] = override_get_current_user
    yield TestClient(app)
    app.dependency_overrides.clear()


def _fake_tier_chain(tier: str, route_profile: str | None = None, task: str = "generic"):
    reachable = route_profile == "openrouter" and tier != "heavy"
    return {
        "tier": tier,
        "route_profile": route_profile,
        "task": task,
        "reachable": reachable,
        "entries": [],
    }


@patch("backend.core.llm_probe.test_tier_chain", side_effect=_fake_tier_chain)
def test_test_all_profiles_returns_matrix(_mock_chain, client: TestClient):
    res = client.post("/api/system/llm/test-all-profiles", json={"task": "generic"})
    assert res.status_code == 202
    data = res.json()
    assert "job_id" in data
    job_id = data["job_id"]

    job_res = client.get(f"/api/system/llm/jobs/{job_id}")
    assert job_res.status_code == 200
    job = job_res.json()
    # immediate mode under pytest → completed
    assert job["status"] == "completed"
    result = job["result"]
    assert "profiles" in result
    assert "summary" in result
    assert result["summary"]["total"] >= 1
    assert "openrouter" in result["profiles"]
    assert result["profiles"]["openrouter"]["reachable"] is True
    assert result["profiles"]["openrouter"]["tiers"]["light"]["reachable"] is True
    assert result["profiles"]["openrouter"]["tiers"]["heavy"]["reachable"] is False
