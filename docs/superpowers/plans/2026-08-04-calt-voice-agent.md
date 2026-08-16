# CALT Voice Agent Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans (inline) or subagent-driven-development. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship a tracker-native push-to-talk + textbox assistant that uses the AI handler, Piper/SAPI speech, calendar tools, and spoken confirm for risky PC actions.

**Architecture:** Modules under `backend/behavior/voice_agent/`; started from `TrackerService.start()` / tray menu; brain via `ollama_generate(task="voice_agent")`; tools allowlisted; confirm state machine for risky ops.

**Tech Stack:** Python, existing LLM gateway, tkinter chat UI, Windows SAPI + optional Piper, optional `pynput` hotkey, planner DB via SessionLocal.

## Global Constraints

- Host = desktop tracker only (no second daemon).
- No arbitrary shell tools.
- Risky tools never run without yes/no confirm.
- Agent failures must not stop tracker poll / hard-block.
- Piper preferred; Windows SAPI fallback if Piper binary/model absent.
- Windows STT when available; textbox always works.

## File map

| File | Role |
|------|------|
| `backend/behavior/voice_agent/__init__.py` | Public `start_voice_agent` / `stop_voice_agent` |
| `backend/behavior/voice_agent/memory.py` | Session + durable memory JSON |
| `backend/behavior/voice_agent/confirm.py` | Pending confirm state machine |
| `backend/behavior/voice_agent/tools.py` | Tool schemas + executors |
| `backend/behavior/voice_agent/brain.py` | Prompt + `ollama_generate` + tool parse |
| `backend/behavior/voice_agent/io_speech.py` | STT / TTS |
| `backend/behavior/voice_agent/chat_ui.py` | Tk chat window |
| `backend/behavior/voice_agent/agent.py` | Orchestrator |
| `backend/core/llm_gateway.py` | Add `voice_agent` to TASK_DEFAULTS |
| `backend/behavior/tracker_tray.py` | Menu: Open Voice Agent |
| `backend/behavior/tracker_service.py` | Start agent worker on tracker start |
| `tests/test_voice_agent_*.py` | Unit tests |

---

### Task 1: Memory + confirm state machine

**Files:**
- Create: `backend/behavior/voice_agent/memory.py`
- Create: `backend/behavior/voice_agent/confirm.py`
- Test: `tests/test_voice_agent_confirm.py`, `tests/test_voice_agent_memory.py`

- [ ] Implement memory load/save under `data/voice_agent/`
- [ ] Implement `PendingConfirm` with yes/no/timeout
- [ ] Tests pass

### Task 2: Tools allowlist + calendar/gate/PC

**Files:**
- Create: `backend/behavior/voice_agent/tools.py`
- Test: `tests/test_voice_agent_tools.py`

- [ ] Safe: `calendar_today`, `calendar_add`, `memory_get`, `memory_set`, `gate_status`
- [ ] Risky: `pc_lock`, `pc_shutdown`, `pc_sleep`, `hard_block_arm`, `hard_block_disarm` — flagged; executor only called after confirm
- [ ] Tests for allowlist + risky flag

### Task 3: Brain + agent loop

**Files:**
- Create: `backend/behavior/voice_agent/brain.py`, `agent.py`
- Modify: `backend/core/llm_gateway.py` (TASK_DEFAULTS)
- Test: `tests/test_voice_agent_brain_parse.py`

- [ ] Parse `TOOL name {json}` lines or JSON tool calls
- [ ] `handle_utterance(text)` → reply string; confirm flow

### Task 4: Speech IO + chat UI + tray wire

**Files:**
- Create: `io_speech.py`, `chat_ui.py`, `__init__.py`
- Modify: `tracker_tray.py`, `tracker_service.py`

- [ ] TTS: Piper if configured else SAPI
- [ ] STT: Windows via speech_recognition if present else skip
- [ ] Hotkey optional via pynput
- [ ] Tray opens chat; agent starts with tracker

### Task 5: Docs + verify

- [ ] Short section in `docs/SETUP_AND_COMMANDS.md`
- [ ] `pytest tests/test_voice_agent_*.py`
