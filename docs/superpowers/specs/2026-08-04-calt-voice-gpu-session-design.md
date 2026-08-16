# CALT Voice — GPU session pipeline (tracker-native)

**Date:** 2026-08-04  
**Status:** Design locked (user confirmed)  
**Host:** Existing `backend/behavior/voice_agent/` inside desktop tracker  
**Extends:** [2026-08-04-calt-voice-agent-design.md](./2026-08-04-calt-voice-agent-design.md)

## Problem

The tracker voice agent works (PTT / chat → brain → tools → TTS) but replies wait for the full LLM completion, STT is SpeechRecognition-only, and there is no clear “session start → work → release” boundary for GPU/VRAM. A separate always-on `voice-assistant/` tree or wake-word daemon would fight thermals on an RTX 5060 8GB laptop.

## Decisions locked

| Topic | Choice |
|-------|--------|
| Trigger | **Hotkey / PTT only** (`Ctrl+Shift+Space`) + chat Mic/Send |
| Wake word | **Out of scope** — no Porcupine, no always-on mic/VAD daemon |
| Architecture | Evolve **existing** `voice_agent/` — not a new tree |
| Session model | Ephemeral: start on PTT/Mic → STT → LLM → TTS → **release** |
| TTS now | Keep **edge-tts → Piper → SAPI**; Kokoro later |
| STT now | Optional **faster-whisper** (CUDA if present); else current STT |
| Brain stream | Ollama `/api/generate` stream (`keep_alive=0`) when local; else full-reply speak |
| Power-cap | Windows `.bat` later — **not** bash |
| Tools / confirm | Unchanged allowlist + spoken confirm gates |

## Non-goals (this lane)

- Wake word / always-on listening  
- Kokoro (or other GPU TTS) in this phase  
- New daemon process  
- Hard-require `faster-whisper` in CI requirements  
- Changing calendar / risky-tool semantics  

## VRAM budget (RTX 5060 Laptop 8GB)

Rough concurrent budget when a voice **session** is active:

| Piece | Typical | Notes |
|-------|---------|--------|
| Local LLM (medium) | 4–6 GB | Prefer one medium model; unload via Ollama `keep_alive=0` after voice turn |
| faster-whisper (small/base) | ~1–2 GB | Load only inside session; `del` + empty CUDA cache after |
| Kokoro (later) | ~0.5–1 GB | Do **not** co-reside with a heavy LLM if VRAM tight — sequential is fine |
| edge-tts / Piper / SAPI | ~0 | CPU / network — safe fallback, always available |

Rules:

1. **No idle VRAM** from voice: models load on session start (or first use in session), release on session end.  
2. Voice path should request Ollama **`keep_alive=0`** on streamed local generates so weights are not pinned after the turn.  
3. Prefer **sequential** GPU use (STT → LLM → TTS) over stacking Whisper + LLM + Kokoro.  
4. If CUDA/whisper unavailable → graceful CPU STT fallback; tracker must not crash.

## Architecture (session-based)

```text
[Ctrl+Shift+Space] or [chat Mic]
        │
        ▼
  begin_session()     ← no listener beyond PTT hotkey registration
        │
        ▼
  STT (faster-whisper if optional dep + CUDA, else SpeechRecognition)
        │
        ▼
  stream LLM tokens ──► SentenceStreamChunker ──► speak sentence-by-sentence
        │                    (edge-tts / piper / sapi)
        ├─ TOOL line detected → mute stream speak; confirm / execute as today
        ▼
  end_session()       ← unload whisper; hotkey thread stays (idle, no mic)
```

Hotkey listener (pynput) may stay registered while the tracker runs; it does **not** open the microphone until the user presses the combo. That is not a wake-word daemon.

## Idle guarantees (gaming / VRAM)

When the tracker is running but voice is idle (no open PTT/Mic/chat turn):

| Resource | Idle state |
|----------|------------|
| faster-whisper | **Not loaded** — loads on first listen in a session; `release_stt_models()` on session end / chat close / stop |
| Kokoro GPU TTS | **Not used** (deferred) |
| edge-tts / Piper / SAPI | **Ephemeral** — no warm engine; each `speak()` opens, plays, exits |
| Mic / VAD | **Off** — capture only inside `listen_once` during a session |
| Ollama (voice path) | Stream + `task=voice_agent` fallback use **`keep_alive=0`** so that turn’s weights are not pinned |
| PTT hotkey | Optional **CPU-only** `pynput` listener (~zero CPU when idle). No models. |

**Silence voice for gaming (tracker stays for distraction tracking):**

1. Tray → **Voice hotkey: OFF (gaming)** — stops listener + releases STT; or  
2. Set `VOICE_AGENT_ENABLED=0` and restart the tracker — no auto-hotkey at all; chat still openable from tray if needed.

**Not controlled by the voice agent:** If you left a model loaded in Ollama Desktop / LM Studio from another chat, that VRAM stays until you unload it there. Voice cannot unload unrelated sessions; it only avoids pinning its own voice turns.

## Components (evolve in place)

| Unit | Role |
|------|------|
| `chunker.py` | Pure-CPU sentence chunker for streaming TTS |
| `session.py` | `begin_session` / `end_session` / resource release hooks |
| `io_speech.py` | Optional faster-whisper; session unload; edge-tts; **TTS modes** `jarvis`/`normal` + optional Jarvis WAV filter |
| `jarvis_filter.py` | Light DSP chain (low-pass, presence, soft sat, tiny room) for jarvis mode only |
| `brain.py` | Streaming generate path + `keep_alive=0`; fallback to `call_brain` |
| `agent.py` | Gate stream-speak until TOOL ruled out; `/voice` mode switch; existing tools/confirm |
| `__init__.py` | Wrap PTT in session; `stop_voice_agent` releases resources |

### TTS modes (Jarvis filter)

Default mode is **`jarvis`**: Edge voice `en-GB-RyanNeural` (or `VOICE_AGENT_VOICE`) plus a subtle post-filter on WAV (butler presence — not a cartoon robot). Mode **`normal`** uses a plainer Edge voice (`en-US-JennyNeural`) at a more natural rate with **no** filter; Piper/SAPI fallbacks also skip the filter. Switch via chat UI buttons, `/voice jarvis|normal`, or `VOICE_AGENT_TTS_MODE`; preference persists under `data/voice_agent/tts_mode.json`. Filter errors never break the tracker — unfiltered audio plays instead.

## Phased build

| Phase | Deliverable | Status |
|-------|-------------|--------|
| 1 | `SentenceStreamChunker` + unit tests | **Now** |
| 2 | Session lifecycle helpers + release on stop/PTT end | **Now** |
| 3 | Optional faster-whisper STT (try/import); stream LLM → chunker → speak | **Now** |
| 4 | Kokoro TTS swap (GPU) behind env; keep edge-tts fallback | **Deferred** |
| 5 | Windows power-cap `.bat` (thermal/power limits) | **Deferred** |

### Phase 4 stub (Kokoro)

Not implemented. Future: `VOICE_AGENT_TTS=kokoro` in `io_speech.speak`, load ONNX/GPU only inside session, unload on end; if missing → edge → piper → sapi.

### Phase 5 stub (power-cap)

Not implemented. Future: `scripts\desktop_tracker\voice_gpu_power_cap.bat` (nvidia-smi / Windows power plan) — no bash.

## Error handling

- Whisper import/CUDA fail → log once; use existing `listen_once` path.  
- Stream unavailable (LM Studio non-stream, OpenRouter-only, etc.) → `call_brain` full text → speak once (or feed whole reply through chunker).  
- Session exception → `end_session` in `finally`; tracker poll loop untouched.  
- Empty STT → “I didn't catch that”; no tools.

## Testing

- Unit: chunker sentence boundaries, flush, empty feed.  
- Unit: session begin/end idempotent; release hooks called.  
- Existing `tests/test_voice_agent.py` must stay green.  
- Manual: restart tracker → `Ctrl+Shift+Space` → short question → sentence-paced TTS.

## Success criteria

- No wake word; mic only during PTT/Mic session.  
- edge-tts (or piper/sapi) still works.  
- Tools + confirm gates unchanged.  
- Optional deps do not break CPU-only CI.  
- Clear session release path documented and hooked.

## Out of scope reminder

**Wake word is explicitly out of scope** for this design and all follow-up phases unless the user reopens it.
