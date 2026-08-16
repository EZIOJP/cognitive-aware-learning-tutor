"""Tests for voice agent confirm + memory + tool parse."""

from backend.behavior.voice_agent.brain import build_system_prompt, parse_tool_line, strip_tool_lines
from backend.behavior.voice_agent.confirm import ConfirmGate
from backend.behavior.voice_agent.tools import is_risky


def test_parse_tool_line_json():
    name, args = parse_tool_line('TOOL calendar_add {"title": "Study", "duration_minutes": 45}')
    assert name == "calendar_add"
    assert args["title"] == "Study"
    assert args["duration_minutes"] == 45


def test_parse_tool_bare():
    name, args = parse_tool_line("TOOL calendar_today")
    assert name == "calendar_today"
    assert args == {}


def test_strip_tool_lines():
    text = "Sure.\nTOOL gate_status\nDone."
    assert "TOOL" not in strip_tool_lines(text)
    assert "Sure." in strip_tool_lines(text)


def test_risky_flags():
    assert is_risky("pc_shutdown")
    assert not is_risky("calendar_today")


def test_confirm_yes_no(monkeypatch):
    gate = ConfirmGate()
    gate.arm("pc_lock", {}, "Lock now?")
    calls = []

    def exe(name, args):
        calls.append(name)
        return "locked"

    reply, handled = gate.resolve("yes", exe)
    assert handled and reply == "locked" and calls == ["pc_lock"]

    gate.arm("pc_shutdown", {}, "Shut down?")
    reply2, handled2 = gate.resolve("no", exe)
    assert handled2 and reply2 == "Cancelled." and calls == ["pc_lock"]


def test_confirm_timeout(monkeypatch):
    gate = ConfirmGate()
    gate.arm("pc_lock", {}, "Lock?")
    gate.pending.created_at -= 100  # type: ignore[union-attr]
    reply, handled = gate.resolve("maybe", lambda n, a: "x")
    assert handled and "timed out" in reply.lower()


def test_memory_roundtrip(tmp_path, monkeypatch):
    from backend.behavior.voice_agent import memory as mem

    monkeypatch.setattr(mem, "_DIR", tmp_path)
    assert mem.memory_get(9) == "(empty)"
    mem.memory_set(9, "name", "Lenovo")
    assert "Lenovo" in mem.memory_get(9)
    assert mem.memory_get(9, "name") == "Lenovo"
    mem.append_turn(9, "user", "hi")
    mem.append_turn(9, "assistant", "hello")
    turns = mem.load_turns(9)
    assert len(turns) == 2


def test_free_mode_pauses_and_restores_voice(monkeypatch):
    from backend.behavior import voice_agent as va

    monkeypatch.setenv("VOICE_AGENT_ENABLED", "1")
    va._hotkey_runtime = None
    va._free_mode_paused = False
    stopped = []
    started = []

    monkeypatch.setattr(va, "stop_voice_agent", lambda: stopped.append(1))
    monkeypatch.setattr(
        va,
        "start_voice_agent",
        lambda uid, enable_hotkey=True: started.append((uid, enable_hotkey)),
    )

    assert va.gate_is_free_mode({"browser": {"mode": "free"}})
    assert va.gate_is_free_mode({"reward_day": True, "browser": {"mode": "study"}})
    assert not va.gate_is_free_mode({"browser": {"mode": "study"}})

    out = va.sync_voice_with_browser_gate({"browser": {"mode": "free"}}, user_id=1)
    assert out["paused"] is True
    assert va.is_free_mode_paused()
    assert not va.voice_runtime_allowed()
    assert stopped

    out2 = va.sync_voice_with_browser_gate({"browser": {"mode": "study"}}, user_id=1)
    assert out2["paused"] is False
    assert not va.is_free_mode_paused()
    assert va.voice_runtime_allowed()
    assert started == [(1, True)]


def test_call_brain_falls_back_to_openrouter(monkeypatch):
    """Local ollama empty + OpenRouter key → llm_complete(route_profile=openrouter)."""
    from backend.behavior.voice_agent.brain import call_brain
    from backend.core.llm_gateway import LlmResult

    monkeypatch.setattr(
        "backend.core.ollama_client.ollama_generate",
        lambda *a, **k: "",
    )

    class _Settings:
        llm_openrouter_api_key = "sk-test-or"

    monkeypatch.setattr("backend.config.get_settings", lambda: _Settings())

    calls: list[dict] = []

    def fake_llm_complete(prompt, **kwargs):
        calls.append(kwargs)
        if kwargs.get("route_profile") == "openrouter":
            return LlmResult(text="Hello from OpenRouter", tier="light", route_profile="openrouter")
        return LlmResult(text=None, tier="light", error="all_failed")

    monkeypatch.setattr("backend.core.llm_gateway.llm_complete", fake_llm_complete)

    text, err = call_brain(user_text="hi", history=[], facts="", gate_line="open")
    assert err is None
    assert text == "Hello from OpenRouter"
    assert any(c.get("route_profile") == "openrouter" for c in calls)


def test_system_prompt_jarvis_light():
    prompt = build_system_prompt(facts="", gate_line="open")
    assert "butler" in prompt.lower() or "Jarvis" in prompt
    assert "sir" in prompt.lower()
    assert "sparingly" in prompt.lower()


def test_tts_preference_env(monkeypatch):
    from backend.behavior.voice_agent import io_speech as io

    monkeypatch.delenv("VOICE_AGENT_TTS", raising=False)
    assert io.tts_preference() == "edge"
    monkeypatch.setenv("VOICE_AGENT_TTS", "PIPER")
    assert io.tts_preference() == "piper"
    monkeypatch.setenv("VOICE_AGENT_TTS", "sapi")
    assert io.tts_preference() == "sapi"
    monkeypatch.setenv("VOICE_AGENT_TTS", "nope")
    assert io.tts_preference() == "edge"


def test_speak_sapi_pref_skips_edge(monkeypatch):
    """VOICE_AGENT_TTS=sapi must not call edge or piper."""
    from backend.behavior.voice_agent import io_speech as io

    monkeypatch.setenv("VOICE_AGENT_TTS", "sapi")
    calls: list[str] = []

    monkeypatch.setattr(io, "_speak_edge", lambda t: calls.append("edge") or True)
    monkeypatch.setattr(io, "_speak_piper", lambda t: calls.append("piper") or True)
    monkeypatch.setattr(io, "_speak_sapi", lambda t: calls.append("sapi"))

    io.speak("hello")
    assert calls == ["sapi"]


def test_speak_edge_fallback_order(monkeypatch):
    """Default path: try edge, then piper, then sapi — no network."""
    from backend.behavior.voice_agent import io_speech as io

    monkeypatch.setenv("VOICE_AGENT_TTS", "edge")
    calls: list[str] = []

    monkeypatch.setattr(io, "_speak_edge", lambda t: calls.append("edge") or False)
    monkeypatch.setattr(io, "_speak_piper", lambda t: calls.append("piper") or False)
    monkeypatch.setattr(io, "_speak_sapi", lambda t: calls.append("sapi"))

    io.speak("hello")
    assert calls == ["edge", "piper", "sapi"]


def test_edge_voice_defaults(monkeypatch, tmp_path):
    from backend.behavior.voice_agent import io_speech as io

    monkeypatch.setattr(io, "_TTS_MODE_PATH", tmp_path / "tts_mode.json")
    monkeypatch.setattr(io, "_runtime_mode", None)
    monkeypatch.delenv("VOICE_AGENT_VOICE", raising=False)
    monkeypatch.delenv("VOICE_AGENT_TTS_MODE", raising=False)
    io.set_tts_mode("jarvis")
    assert io.edge_voice() == io.DEFAULT_EDGE_VOICE
    monkeypatch.setenv("VOICE_AGENT_VOICE", "en-GB-ThomasNeural")
    assert io.edge_voice() == "en-GB-ThomasNeural"


def test_tts_mode_persistence(monkeypatch, tmp_path):
    from backend.behavior.voice_agent import io_speech as io

    monkeypatch.setattr(io, "_TTS_MODE_PATH", tmp_path / "tts_mode.json")
    monkeypatch.setattr(io, "_runtime_mode", None)
    monkeypatch.delenv("VOICE_AGENT_TTS_MODE", raising=False)
    assert io.get_tts_mode() == "jarvis"
    assert io.set_tts_mode("normal") == "normal"
    assert io.get_tts_mode() == "normal"
    assert (tmp_path / "tts_mode.json").is_file()
    monkeypatch.setattr(io, "_runtime_mode", None)
    assert io.get_tts_mode() == "normal"
    monkeypatch.setenv("VOICE_AGENT_TTS_MODE", "jarvis")
    assert io.get_tts_mode() == "jarvis"


def test_edge_voice_follows_mode(monkeypatch, tmp_path):
    from backend.behavior.voice_agent import io_speech as io

    monkeypatch.setattr(io, "_TTS_MODE_PATH", tmp_path / "tts_mode.json")
    monkeypatch.setattr(io, "_runtime_mode", None)
    monkeypatch.delenv("VOICE_AGENT_VOICE", raising=False)
    monkeypatch.delenv("VOICE_AGENT_TTS_MODE", raising=False)
    io.set_tts_mode("normal")
    assert io.edge_voice() == io.NORMAL_EDGE_VOICE
    assert io.edge_rate() == io.NORMAL_EDGE_RATE
    io.set_tts_mode("jarvis")
    assert io.edge_voice() == io.DEFAULT_EDGE_VOICE


def test_jarvis_filter_on_sine(tmp_path):
    import math
    import struct
    import wave

    from backend.behavior.voice_agent.jarvis_filter import apply_jarvis_filter, jarvis_process_mono
    import numpy as np

    sr = 16000
    n = sr // 2
    samples = [int(16000 * math.sin(2 * math.pi * 440 * i / sr)) for i in range(n)]
    src = tmp_path / "sine.wav"
    with wave.open(str(src), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        wf.writeframes(struct.pack(f"<{n}h", *samples))

    out = apply_jarvis_filter(src, out_path=tmp_path / "sine_j.wav")
    assert out.is_file() and out.stat().st_size > 44
    arr = np.array(samples, dtype=np.float64)
    filtered = jarvis_process_mono(arr, sr)
    assert filtered.shape == arr.shape
    assert np.isfinite(filtered).all()


def test_speak_edge_jarvis_calls_filter(monkeypatch, tmp_path):
    from backend.behavior.voice_agent import io_speech as io

    monkeypatch.setattr(io, "_TTS_MODE_PATH", tmp_path / "tts_mode.json")
    monkeypatch.setattr(io, "_runtime_mode", None)
    monkeypatch.delenv("VOICE_AGENT_TTS_MODE", raising=False)
    monkeypatch.setenv("VOICE_AGENT_TTS", "edge")
    io.set_tts_mode("jarvis")

    calls: list[str] = []

    def fake_edge(text: str) -> bool:
        calls.append("edge")
        # Simulate edge path internals via public helpers
        wav = tmp_path / "t.wav"
        import math
        import struct
        import wave

        n = 800
        sr = 16000
        samples = [int(8000 * math.sin(2 * math.pi * 200 * i / sr)) for i in range(n)]
        with wave.open(str(wav), "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(sr)
            wf.writeframes(struct.pack(f"<{n}h", *samples))
        play = io._maybe_jarvis_filter_wav(wav)
        calls.append("filtered" if play != wav else "raw")
        return True

    monkeypatch.setattr(io, "_speak_edge", fake_edge)
    monkeypatch.setattr(io, "_speak_piper", lambda t: False)
    monkeypatch.setattr(io, "_speak_sapi", lambda t: None)
    io.speak("hello")
    assert "edge" in calls
    assert "filtered" in calls


def test_speak_normal_skips_filter(monkeypatch, tmp_path):
    """Normal mode must not rewrite the WAV through the Jarvis DSP."""
    import struct
    import wave

    from backend.behavior.voice_agent import io_speech as io
    from backend.behavior.voice_agent import jarvis_filter as jf

    monkeypatch.setattr(io, "_TTS_MODE_PATH", tmp_path / "tts_mode.json")
    monkeypatch.setattr(io, "_TTS_DIR", tmp_path)
    monkeypatch.setattr(io, "_runtime_mode", None)
    monkeypatch.delenv("VOICE_AGENT_TTS_MODE", raising=False)
    io.set_tts_mode("normal")

    applied: list[str] = []
    real_apply = jf.apply_jarvis_filter

    def tracking(path, **kwargs):
        applied.append(str(path))
        return real_apply(path, **kwargs)

    monkeypatch.setattr(jf, "apply_jarvis_filter", tracking)

    wav = tmp_path / "n.wav"
    n, sr = 400, 8000
    samples = [1000] * n
    with wave.open(str(wav), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        wf.writeframes(struct.pack(f"<{n}h", *samples))

    out = io._maybe_jarvis_filter_wav(wav)
    assert out == wav
    assert applied == []

    io.set_tts_mode("jarvis")
    out2 = io._maybe_jarvis_filter_wav(wav)
    assert applied, "jarvis mode should call apply_jarvis_filter"
    assert out2.is_file()


def test_voice_slash_command(monkeypatch, tmp_path):
    from backend.behavior.voice_agent.agent import VoiceAgent
    from backend.behavior.voice_agent import io_speech as io
    from backend.behavior.voice_agent import memory as mem

    monkeypatch.setattr(io, "_TTS_MODE_PATH", tmp_path / "tts_mode.json")
    monkeypatch.setattr(io, "_runtime_mode", None)
    monkeypatch.setattr(mem, "_DIR", tmp_path)
    monkeypatch.delenv("VOICE_AGENT_TTS_MODE", raising=False)

    spoken: list[str] = []
    monkeypatch.setattr(io, "speak", lambda t: spoken.append(t))
    # agent imports speak at module level — patch there too
    monkeypatch.setattr("backend.behavior.voice_agent.agent.speak", lambda t: spoken.append(t))

    agent = VoiceAgent(user_id=42)
    out = agent.handle_utterance("/voice", say=False)
    assert "jarvis" in out.lower() or "Voice mode" in out

    out2 = agent.handle_utterance("/voice normal", say=True)
    assert "normal" in out2.lower()
    assert io.get_tts_mode() == "normal"
    assert any("Normal" in s or "normal" in s.lower() for s in spoken)

    out3 = agent.handle_utterance("/voice jarvis", say=False)
    assert "jarvis" in out3.lower()
    assert io.get_tts_mode() == "jarvis"

    out4 = agent.handle_utterance("/voice nope", say=False)
    assert "Usage" in out4


def test_emit_ui_before_speak(monkeypatch, tmp_path):
    """Reply text reaches on_reply before any TTS (text-before-audio)."""
    from backend.behavior.voice_agent.agent import VoiceAgent
    from backend.behavior.voice_agent import memory as mem

    monkeypatch.setattr(mem, "_DIR", tmp_path)
    order: list[str] = []

    monkeypatch.setattr(
        "backend.behavior.voice_agent.agent.speak",
        lambda t: order.append(f"speak:{t}"),
    )

    agent = VoiceAgent(user_id=7)
    agent.on_reply = lambda t: order.append(f"ui:{t}")
    out = agent._emit("Hello world.", say=True)
    assert out == "Hello world."
    assert order == ["ui:Hello world.", "speak:Hello world."]


def test_emit_stream_gate_ui_before_flush_speak(monkeypatch, tmp_path):
    """Stream path: buffer sentences → UI → then flush_speak."""
    from backend.behavior.voice_agent.agent import VoiceAgent, _StreamSpeakGate
    from backend.behavior.voice_agent import memory as mem

    monkeypatch.setattr(mem, "_DIR", tmp_path)
    order: list[str] = []

    def track_speak(t: str) -> None:
        order.append(f"speak:{t}")

    monkeypatch.setattr("backend.behavior.voice_agent.agent.speak", track_speak)

    agent = VoiceAgent(user_id=8)
    agent.on_reply = lambda t: order.append(f"ui:{t}")
    gate = _StreamSpeakGate(track_speak)
    gate.feed("Hello there. ")
    gate.feed("All good.")
    gate.finish()
    assert not any(x.startswith("speak:") for x in order)
    agent._emit("Hello there. All good.", say=True, gate=gate)
    assert order[0] == "ui:Hello there. All good."
    assert any(x.startswith("speak:") for x in order)
    assert order.index("ui:Hello there. All good.") < min(
        i for i, x in enumerate(order) if x.startswith("speak:")
    )


def test_emit_speak_failure_still_shows_ui(monkeypatch, tmp_path):
    from backend.behavior.voice_agent.agent import VoiceAgent
    from backend.behavior.voice_agent import memory as mem

    monkeypatch.setattr(mem, "_DIR", tmp_path)
    shown: list[str] = []

    def boom(_t: str) -> None:
        raise RuntimeError("tts down")

    monkeypatch.setattr("backend.behavior.voice_agent.agent.speak", boom)
    agent = VoiceAgent(user_id=9)
    agent.on_reply = shown.append
    out = agent._emit("Still visible.", say=True)
    assert out == "Still visible."
    assert shown == ["Still visible."]


def test_open_app_rejects_unknown():
    from backend.behavior.voice_agent.tools import execute_tool

    out = execute_tool(1, "open_app", {"name": "malware.exe"})
    assert out.startswith("error:")
    assert "allowlist" in out.lower() or "unknown" in out.lower()


def test_open_url_rejects_non_http():
    from backend.behavior.voice_agent.tools import execute_tool

    for bad in ("javascript:alert(1)", "file:///C:/Windows/System32", "ftp://example.com"):
        out = execute_tool(1, "open_url", {"url": bad})
        assert out.startswith("error:"), bad


def test_web_search_opens_safe_url(monkeypatch):
    from backend.behavior.voice_agent import tools as tools_mod

    opened: list[str] = []
    monkeypatch.setattr(tools_mod.webbrowser, "open", lambda url: opened.append(url) or True)

    out = tools_mod.execute_tool(1, "web_search", {"query": "numpy broadcast"})
    assert not out.startswith("error:")
    assert opened, "expected webbrowser.open call"
    url = opened[0]
    assert url.startswith("https://")
    assert "duckduckgo.com" in url or "bing.com" in url
    assert "numpy" in url.lower() or "broadcast" in url.lower()


def test_pc_lock_still_risky():
    assert is_risky("pc_lock")
    assert is_risky("pc_sleep")
    from backend.behavior.voice_agent.tools import TOOL_SPECS

    names = {t["name"] for t in TOOL_SPECS}
    assert "web_search" in names
    assert "open_url" in names
    assert "open_app" in names
    assert "play_music" in names
    assert "system_info" in names
    assert "volume_mute" in names or "set_volume" in names or "volume_up" in names


def test_call_brain_stream_falls_back(monkeypatch):
    from backend.behavior.voice_agent import brain as brain_mod

    monkeypatch.setattr(brain_mod, "try_stream_local", lambda *a, **k: None)
    monkeypatch.setattr(
        brain_mod,
        "call_brain",
        lambda **k: ("Full reply here.", None),
    )
    tokens: list[str] = []
    text, err = brain_mod.call_brain_stream(
        user_text="hi",
        history=[],
        facts="",
        gate_line="open",
        on_token=tokens.append,
    )
    assert err is None
    assert text == "Full reply here."
    assert tokens == ["Full reply here."]


def test_tools_prompt_lists_new_actions():
    from backend.behavior.voice_agent.tools import tools_prompt_block

    block = tools_prompt_block()
    assert "web_search" in block
    assert "open_app" in block
    assert "play_music" in block
    assert "[RISKY-CONFIRM]" in block
    assert "pc_lock" in block
