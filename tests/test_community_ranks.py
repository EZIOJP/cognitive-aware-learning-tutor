"""Opt-in Tailscale ranks — off by default, private data never published."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from backend.community.network import peer_url_allowed, public_base_from_peer
from backend.community.store import default_settings, load_settings, save_settings


def test_publish_ranks_defaults_off(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    path = tmp_path / "community.json"
    monkeypatch.setattr("backend.community.store.SETTINGS_PATH", path)
    s = load_settings()
    assert s["publish_ranks"] is False
    assert s["peers"] == []


def test_device_urls_include_whole_site():
    from backend.community.network import device_urls

    urls = device_urls({"ipv4": ["100.64.1.2"], "magicdns": "box.tail1234.ts.net"})
    assert "http://100.64.1.2:5173" in urls["tailscale_site"]
    assert "http://box.tail1234.ts.net:5173" in urls["tailscale_site"]
    assert "http://100.64.1.2:8000" in urls["tailscale_api"]
    assert urls["tailscale"][0]["site"].endswith(":5173")


def test_peer_url_allowlist():
    assert peer_url_allowed("http://100.64.1.2:8000")
    assert peer_url_allowed("http://100.100.10.20:8000/")
    assert peer_url_allowed("https://box.tail1234.ts.net")
    assert peer_url_allowed("http://192.168.1.10:8000")
    assert peer_url_allowed("http://127.0.0.1:8000")
    assert not peer_url_allowed("https://evil.example.com")
    assert not peer_url_allowed("http://8.8.8.8:8000")
    assert not peer_url_allowed("ftp://100.64.1.2:8000")
    assert public_base_from_peer("http://100.64.1.2:8000/foo") == "http://100.64.1.2:8000"


def test_save_settings_keeps_opt_in_explicit(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    path = tmp_path / "community.json"
    monkeypatch.setattr("backend.community.store.SETTINGS_PATH", path)
    save_settings({**default_settings(), "publish_ranks": True, "peers": ["http://100.64.1.2:8000"]})
    s = load_settings()
    assert s["publish_ranks"] is True
    assert s["peers"] == ["http://100.64.1.2:8000"]
    save_settings({**s, "publish_ranks": False})
    assert load_settings()["publish_ranks"] is False


def test_public_card_404_when_not_published(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    from fastapi.testclient import TestClient

    from backend.main import app

    path = tmp_path / "community.json"
    monkeypatch.setattr("backend.community.store.SETTINGS_PATH", path)
    save_settings(default_settings())
    r = TestClient(app).get("/api/community/public-card")
    assert r.status_code == 404


def test_public_card_ok_when_opted_in(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    from fastapi.testclient import TestClient

    from backend.main import app

    path = tmp_path / "community.json"
    monkeypatch.setattr("backend.community.store.SETTINGS_PATH", path)
    save_settings({**default_settings(), "publish_ranks": True})
    r = TestClient(app).get("/api/community/public-card")
    assert r.status_code == 200
    body = r.json()
    assert "display_name" in body
    assert "pulse" in body
    assert "notes" not in body
    assert "sessions" not in body
