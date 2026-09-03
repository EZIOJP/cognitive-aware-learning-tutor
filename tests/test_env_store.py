"""Tests for .env key storage."""

from pathlib import Path

import pytest

from backend.core import env_store


@pytest.fixture
def isolated_env(tmp_path, monkeypatch):
    env_path = tmp_path / ".env"
    env_path.write_text("LLM_ROUTE_PROFILE=hybrid\n# comment\nOTHER=keep\n", encoding="utf-8")
    backup_path = tmp_path / ".env.bak"
    monkeypatch.setattr(env_store, "ENV_PATH", env_path)
    monkeypatch.setattr(env_store, "ENV_BACKUP_PATH", backup_path)
    return env_path


def test_patch_env_updates_and_preserves_comments(isolated_env: Path):
    written = env_store.patch_env({"LLM_ROUTE_PROFILE": "local", "LLM_OPENROUTER_API_KEY": "sk-test"})
    assert "LLM_ROUTE_PROFILE" in written
    assert "LLM_OPENROUTER_API_KEY" in written
    text = isolated_env.read_text(encoding="utf-8")
    assert "LLM_ROUTE_PROFILE=local" in text
    assert "LLM_OPENROUTER_API_KEY=" in text
    assert "# comment" in text
    assert "OTHER=keep" in text


def test_patch_env_rejects_unknown_keys(isolated_env: Path):
    written = env_store.patch_env({"JWT_SECRET": "hacked", "LLM_API_KEY": "lm-studio"})
    assert written == ["LLM_API_KEY"]
