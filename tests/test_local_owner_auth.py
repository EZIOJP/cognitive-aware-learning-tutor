"""Solo owner: local-session + profile display_name (no password)."""

from fastapi.testclient import TestClient

from backend.main import app

client = TestClient(app)


def test_auth_me_solo_without_token():
    r = client.get("/api/vocab/auth/me")
    assert r.status_code == 200
    body = r.json()
    assert body["username"] == "admin"
    assert "display_name" in body
    assert body.get("is_admin") is True


def test_local_session_mints_token_without_password():
    r = client.get("/api/vocab/auth/local-session")
    assert r.status_code == 200
    data = r.json()
    assert data["user"]["username"] == "admin"
    assert isinstance(data["token"], str) and len(data["token"]) > 10
    me = client.get(
        "/api/vocab/auth/me",
        headers={"Authorization": f"Bearer {data['token']}"},
    )
    assert me.status_code == 200
    assert me.json()["username"] == "admin"


def test_local_session_forbidden_when_not_solo(monkeypatch):
    from backend.config import get_settings

    settings = get_settings()
    monkeypatch.setattr(settings, "solo_local_user", False)
    r = client.get("/api/vocab/auth/local-session")
    assert r.status_code == 403


def test_patch_display_name_roundtrip():
    me0 = client.get("/api/vocab/auth/me")
    assert me0.status_code == 200
    original = me0.json().get("display_name")
    sess = client.get("/api/vocab/auth/local-session")
    token = sess.json()["token"]
    headers = {"Authorization": f"Bearer {token}"}
    try:
        r = client.patch(
            "/api/vocab/auth/me",
            json={"display_name": "Captain Focus"},
            headers=headers,
        )
        assert r.status_code == 200
        assert r.json()["display_name"] == "Captain Focus"
        again = client.get("/api/vocab/auth/me", headers=headers)
        assert again.json()["display_name"] == "Captain Focus"
    finally:
        client.patch(
            "/api/vocab/auth/me",
            json={"display_name": original},
            headers=headers,
        )
