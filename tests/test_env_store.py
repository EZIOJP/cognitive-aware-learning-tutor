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


def test_resolve_agent_manual():
    from backend.hub.agents.cortex import resolve_agent

    agent, trace = resolve_agent("coding", prompt="hello")
    assert agent == "coding"
    assert trace[0] == "manual:coding"


def test_resolve_agent_pdf_mime():
    from backend.hub.agents.cortex import resolve_agent

    agent, trace = resolve_agent("auto", prompt="summarize", content_type="application/pdf")
    assert agent == "pdf_rag"


def test_session_rag_chunk_and_retrieve():
    from backend.hub.agents.session_rag import ingest_upload, retrieve, clear_session

    sid = "test-session"
    count = ingest_upload(sid, "notes.txt", b"numpy arrays and linear algebra vectors", "text/plain")
    assert count >= 1
    hits = retrieve(sid, "numpy linear", top_k=2)
    assert hits
    clear_session(sid)
