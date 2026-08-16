# CALT Voice Agent (tracker-native) — design

**Date:** 2026-08-04  
**Status:** Ready for user review  
**Host:** Desktop Activity Tracker (always-on)  
**Bar for “perfect”:** doesn’t crash; doesn’t act destructively on a misheard command; remembers the user correctly.

## Problem

CALT already has an LLM gateway, planner/calendar APIs, AI Coach (text), and a 24/7 desktop tracker. What’s missing is a **single voice-first assistant**: talk (or type) → one brain → tools → speak/text reply — not a separate automation platform.

## Goals (v1)

1. Push-to-talk hotkey **and** a small text chat box (tray / tiny window).
2. Brain via existing **AI handler** (`ollama_generate` → `llm_complete`), local LM Studio/Ollama first.
3. Speak replies with **Piper** TTS (CPU-light; does not compete for LLM VRAM).
4. Hear via **Windows speech recognition** on PTT release.
5. Agent process lives **inside the desktop tracker** (no second 24/7 daemon).
6. First real tool: **calendar / planner** (read today, add/confirm blocks).
7. Risky tools (sleep, shutdown, lock, hard-block changes): **spoken confirm** — agent asks out loud, waits for yes/no via PTT or text before executing.
8. Short memory of recent turns + user facts stored in CALT (SQLite / small JSON), not a second brain.

## Non-goals (v1)

- Wake word (“Hey CALT”).
- Claude/Anthropic-required path (optional later via gateway only).
- Heavy TTS (VoxCPM, Higgs, VibeVoice, Orpheus) — storytelling-class models.
- React Native / mobile executorch stacks.
- Full home automation / lights (later tool).
- Replacing AI Coach web page (can share memory later; v1 UI is tracker-side).
- “Polish everything” (morning gate UX polish, extension polish) — separate track.

## Decisions locked

| Topic | Choice |
|-------|--------|
| Interaction | PTT hotkey + textbox |
| Host | Desktop tracker process |
| Brain | AI handler task `voice_agent` (local tiers) |
| TTS | Piper |
| STT | Windows speech (PTT) |
| Risky actions | Spoken confirm → yes/no |
| Architecture style | One agent loop + incremental tools |

## Architecture

```text
[PTT hotkey] or [textbox]
       │
       ▼
 Desktop tracker — voice_agent module
       │  STT (Windows) if audio
       ▼
 ollama_generate(task="voice_agent", tools=...)
       │
       ├─ tool_calls → calendar / memory / (risky → confirm gate)
       │
       ▼
 reply text → Piper TTS + show in chat box
```

### Components (files — conceptual)

| Unit | Responsibility |
|------|----------------|
| `tracker_voice_agent.py` | Session loop: ingest utterance, call brain, run tools, speak |
| `tracker_voice_io.py` | PTT hotkey, Windows STT, Piper TTS playback |
| `tracker_voice_tools.py` | Tool schemas + executors (calendar first; risky tools behind confirm) |
| `tracker_voice_memory.py` | Load/save recent turns + durable notes (user-scoped) |
| Tray / small UI | Chat history + text input + status (listening / thinking / speaking) |
| Gateway | New task `voice_agent` → medium tier default (configurable in AI Control Center) |

Tracker already owns hub remotes (`/api/hub/shutdown`, `/api/hub/lock`). Risky tools should call the **same** implementations after confirm, not duplicate OS calls.

### Data flow

1. User holds configured hotkey (default e.g. `Ctrl+Shift+Space`) or types in the box.
2. On release: STT → transcript; or use typed text as-is.
3. Append to short context (last N turns + memory summary + “today” planner snapshot).
4. `ollama_generate(..., task="voice_agent")` with tool definitions (JSON tool-calling if model supports it; else constrained “TOOL: name args” parse with strict allowlist).
5. For each tool:
   - **Safe:** run immediately; return result to model for final reply.
   - **Risky:** do not run; speak confirm prompt; set `pending_confirm` state; next utterance yes/no resolves or cancels.
6. Final reply → Piper + UI.
7. Persist turn to memory store.

### Error handling

- STT empty / garbage → speak “I didn’t catch that” ; no tools.
- Gateway/local model down → speak “Brain offline — check LM Studio / AI Control Center”; no tools.
- Piper missing → show text only; log once; don’t crash tracker poll loop.
- Tool failure → speak short error; never retry destructive tools automatically.
- Agent exceptions isolated in a thread/async worker so **tracking / hard-block keep running**.

### Safety

- Allowlist tools only (no arbitrary shell).
- Risky set (v1): `pc_sleep`, `pc_shutdown`, `pc_lock`, `hard_block_arm`, `hard_block_disarm` — each requires spoken confirm matching yes/no (accept “yes”, “yeah”, “confirm”, “no”, “cancel”).
- Confirm times out after ~45s → cancel.
- Misheard command that maps to risky tool still hits confirm (never one-shot sleep).
- Calendar write tools are “soft risky”: v1 can run without confirm if title/time are explicit; optional confirm later.

### Memory

- **Ephemeral:** last 8–12 turns in process + on disk under `data/voice_agent/session_{user}.json`.
- **Durable notes:** small key-value / bullet list in SQLite or `data/voice_agent/memory_{user}.json` (name, preferences, standing tasks). Exposed as tools `memory_get` / `memory_set`.
- Do not dump entire tracked_sessions history into every prompt — summarize “now playing” / gate status as a short system line from existing tracker state.

### First tools (v1)

1. `calendar_today` — list today’s planner blocks  
2. `calendar_add` — add a block (title, start, duration)  
3. `memory_get` / `memory_set`  
4. `gate_status` — read distraction/morning gate (read-only)  
5. Risky (confirm): `pc_lock`, `pc_sleep` (if available), `pc_shutdown` (reuse hub behavior)

### Testing

- Unit: tool allowlist; confirm state machine (yes/no/timeout); no execute without confirm.  
- Unit: memory round-trip.  
- Integration (optional): mock `ollama_generate` → tool call → calendar list.  
- Manual: PTT → “what’s on my calendar today?” → Piper reply; text box same; “shutdown the PC” → spoken confirm → “no” cancels.

### Success criteria

- Tracker stays up with agent idle (no meaningful CPU/VRAM from Piper when silent).  
- PTT + text both work.  
- Calendar Q&A works with local model via AI handler.  
- Shutdown/sleep never runs without confirm.  
- One clear tray entry point; no second always-on exe.

### Canned dialogue (shipped)

Routine speech is **not** LLM: `dialogues.py` + `block_dialogues.py` (gate blocks). Morning brief once/day + `/brief`. Free chat / tools still use the brain; system prompt notes rituals are spoken separately.

## Out of scope follow-ups

- Kokoro TTS swap — see [2026-08-04-calt-voice-gpu-session-design.md](./2026-08-04-calt-voice-gpu-session-design.md) phase 4  
- Sherpa STT / optional faster-whisper (GPU session phases)  
- **Wake word — explicitly out of scope** (hotkey/PTT only)  
- Lights / IoT  
- Watch Sync as remote mic  
- Morning-gate / SelfTracker polish (separate)

## Open config (defaults, not blockers)

- Hotkey: `Ctrl+Shift+Space` (user-overridable in `tracker.json`)  
- TTS: `edge-tts` neural default `en-GB-RyanNeural` (Jarvis-adjacent); override `VOICE_AGENT_TTS` / `VOICE_AGENT_VOICE`; Piper under `data/voice_agent/piper/` then SAPI  
- `MORNING_GATE` / hard-block unchanged by agent unless user confirms risky tool  
