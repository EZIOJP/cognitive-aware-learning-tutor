"""Tests for sentence chunker + voice session lifecycle."""

from backend.behavior.voice_agent.chunker import SentenceStreamChunker
from backend.behavior.voice_agent.session import (
    begin_session,
    end_session,
    get_active_session,
    release_session_resources,
    voice_session,
)


def test_chunker_sentence_by_sentence():
    c = SentenceStreamChunker(min_chars=4)
    assert c.feed("Hello there. ") == ["Hello there."]
    assert c.feed("How are you? ") == ["How are you?"]
    assert c.flush() == []


def test_chunker_holds_incomplete():
    c = SentenceStreamChunker(min_chars=4)
    assert c.feed("Hello") == []
    assert c.feed(" world") == []
    assert c.feed(". Next") == ["Hello world."]
    assert c.flush() == ["Next"]


def test_chunker_empty_feed():
    c = SentenceStreamChunker()
    assert c.feed("") == []
    assert c.flush() == []


def test_chunker_exclamation_and_ellipsis():
    c = SentenceStreamChunker(min_chars=2)
    assert c.feed("Wow! ") == ["Wow!"]
    assert c.feed("Wait… ") == ["Wait…"]


def test_chunker_decimal_not_sentence():
    c = SentenceStreamChunker(min_chars=4)
    assert c.feed("It is 3.14 approximately. ") == ["It is 3.14 approximately."]


def test_stream_speak_gate_mutes_tool():
    from backend.behavior.voice_agent.agent import _StreamSpeakGate

    spoken: list[str] = []
    g = _StreamSpeakGate(spoken.append)
    g.feed("TOOL calendar_today\n")
    g.feed("ignored")
    assert g.finish().startswith("TOOL")
    assert spoken == []
    assert not g.spoken


def test_stream_speak_gate_speaks_sentences():
    """Sentences buffer during feed; speak only on flush_speak (after UI)."""
    from backend.behavior.voice_agent.agent import _StreamSpeakGate

    spoken: list[str] = []
    g = _StreamSpeakGate(spoken.append)
    g.feed("Hello there. ")
    g.feed("All good.")
    out = g.finish()
    assert "Hello" in out
    assert spoken == []  # not yet — text-before-audio
    assert not g.spoken
    g.flush_speak()
    assert spoken
    assert g.spoken


def test_session_lifecycle(monkeypatch):
    released: list[bool] = []

    def fake_release():
        released.append(True)

    monkeypatch.setattr(
        "backend.behavior.voice_agent.io_speech.release_stt_models",
        fake_release,
    )
    # end_session imports release via session.release_session_resources
    monkeypatch.setattr(
        "backend.behavior.voice_agent.session.release_session_resources",
        fake_release,
    )

    s = begin_session(user_id=1, trigger="test")
    assert get_active_session() is s
    end_session(s)
    assert get_active_session() is None
    assert released


def test_voice_session_context(monkeypatch):
    released: list[bool] = []
    monkeypatch.setattr(
        "backend.behavior.voice_agent.session.release_session_resources",
        lambda: released.append(True),
    )
    with voice_session(user_id=2, trigger="ctx") as s:
        assert get_active_session() is s
    assert get_active_session() is None
    assert released


def test_release_session_resources_safe():
    # Must not raise when whisper never loaded
    release_session_resources()


def test_stt_model_not_resident_after_release(monkeypatch):
    """No global Whisper singleton may survive session release."""
    from backend.behavior.voice_agent import io_speech as io

    sentinel = object()
    monkeypatch.setattr(io, "_whisper_model", sentinel)
    assert io.stt_model_resident() is True
    io.release_stt_models()
    assert io.stt_model_resident() is False
    assert io._whisper_model is None


def test_voice_agent_enabled_env(monkeypatch):
    from backend.behavior import voice_agent as va

    monkeypatch.setenv("VOICE_AGENT_ENABLED", "0")
    assert va.voice_agent_enabled() is False
    monkeypatch.setenv("VOICE_AGENT_ENABLED", "false")
    assert va.voice_agent_enabled() is False
    monkeypatch.setenv("VOICE_AGENT_ENABLED", "1")
    assert va.voice_agent_enabled() is True
    monkeypatch.delenv("VOICE_AGENT_ENABLED", raising=False)
    assert va.voice_agent_enabled() is True


def test_set_voice_hotkey_off_releases(monkeypatch):
    from backend.behavior import voice_agent as va
    from backend.behavior.voice_agent import io_speech as io

    released: list[bool] = []
    monkeypatch.setattr(va, "_hotkey_runtime", None)
    monkeypatch.setattr(va, "voice_agent_enabled", lambda: True)
    monkeypatch.setattr(va, "stop_hotkey", lambda: None)
    monkeypatch.setattr(io, "release_stt_models", lambda: released.append(True))
    # set_voice_hotkey_enabled imports release via session
    monkeypatch.setattr(
        "backend.behavior.voice_agent.session.release_session_resources",
        lambda: released.append(True),
    )

    assert va.set_voice_hotkey_enabled(False) is False
    assert va.is_voice_hotkey_enabled() is False
    assert released
    # restore so other tests are not poisoned
    monkeypatch.setattr(va, "_hotkey_runtime", None)


def test_voice_keep_alive_constant():
    """Stream path must request Ollama unload after voice turn."""
    from backend.behavior.voice_agent import brain

    assert brain._VOICE_KEEP_ALIVE == 0
