# CALT Voice Agent (tracker-native)

Runs inside the desktop tracker. Tray → **Voice agent (chat)**.

## Use

1. Start tracker (`scripts\desktop_tracker\run_desktop_tracker.bat`).
2. Start API so the AI handler can reach LM Studio/Ollama.
3. Right-click tray → **Voice agent (chat)** — type or use **Mic**.
4. Optional hotkey: `Ctrl+Shift+Space` (needs `pip install pynput`).
5. Chat `/brief` — canned morning-style brief (goals / bible-plan nudge / yesterday stats). No LLM.
6. Auto morning brief: once per calendar day after 5am when tracker sees bible/plan pending, or on first chat open.

### Canned dialogues (prefer over LLM)

Routine speech uses pools in `dialogues.py` + `block_dialogues.py` (gate blocks). Overrides: `data/voice_agent/dialogues.json` / `block_lines.json`. LLM only for free chat / tools.

### Idle / gaming

Tracker start registers a **CPU-only** hotkey listener — it does **not** preload Whisper, TTS, or LLM.

- Tray → **Voice hotkey: OFF (gaming)** — stop PTT + release STT; distraction tracking continues.
- Env `VOICE_AGENT_ENABLED=0` (restart tracker) — skip auto-hotkey entirely.
- Closing the chat window releases session STT if any was left loaded.

Ollama/LM Studio models you loaded outside voice are **not** unloaded by the agent — use their UIs if VRAM is still occupied.

## Speech

- **TTS modes:** `jarvis` (default) | `normal` — switch in chat UI (**Jarvis** / **Normal**), chat `/voice jarvis` | `/voice normal` | `/voice`, or env `VOICE_AGENT_TTS_MODE`.
  - **jarvis:** `en-GB-RyanNeural` + light DSP post-filter (low-pass / presence / soft sat / tiny room). Filter needs WAV (Piper always; Edge via ffmpeg or WinRT convert — fail soft → unfiltered).
  - **normal:** `en-US-JennyNeural`, natural rate, **no** filter.
  - Preference file: `data/voice_agent/tts_mode.json`
- **TTS engine (preferred):** Microsoft neural via `edge-tts`. Needs network once per utterance.
  - Install: `pip install edge-tts`
  - Env: `VOICE_AGENT_TTS=edge|piper|sapi` (default `edge`), `VOICE_AGENT_VOICE=…` (overrides mode default), optional `VOICE_AGENT_TTS_RATE`, `VOICE_AGENT_TTS_PITCH`
  - Fallback order: Edge → Piper (`data/voice_agent/piper/`) → Windows SAPI
  - Kokoro GPU TTS: deferred (see GPU session spec)
- **STT:** Mic / hotkey only (no wake word). Optional `pip install faster-whisper` (+ CUDA) for session-scoped Whisper; else `SpeechRecognition` / PyAudio.
  - Env: `VOICE_AGENT_WHISPER_MODEL=base`, `VOICE_AGENT_WHISPER_DEVICE=cuda|cpu`
- **Session:** each PTT/Mic/text turn loads STT as needed and releases on end; local Ollama stream **and** `task=voice_agent` fallback use `keep_alive=0`.
- **Disable:** `VOICE_AGENT_ENABLED=0` or tray **Voice hotkey: OFF (gaming)**.

Specs:
- `docs/superpowers/specs/2026-08-04-calt-voice-agent-design.md`
- `docs/superpowers/specs/2026-08-04-calt-voice-gpu-session-design.md`
