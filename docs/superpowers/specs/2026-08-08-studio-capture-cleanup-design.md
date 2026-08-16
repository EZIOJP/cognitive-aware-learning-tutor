# Studio Capture Cleanup Design

**Date:** 2026-08-08  
**Status:** Implemented

## Problem

1. Starting Live Captions mid-lecture dumped the whole on-screen buffer into the transcript (duplication).  
2. `pywinauto` connect-by-path could hang.  
3. Whisper felt secondary; Hindi/English mixed lectures needed a clear bilingual default.  
4. Capture UI was crowded; overnight runs lacked a readable live text feed.

## Decisions

| Topic | Choice |
|-------|--------|
| Live Captions text | Seed current panel on connect; record **deltas only** |
| UIA attach | HWND (`FindWindow`) → PID → title (no path connect) |
| Languages | One multilingual Whisper model, language **auto** (Hinglish) |
| UI | Capture step only: Captions \| Whisper, Advanced collapsed, shared live feed |

## Architecture

```text
Live Captions.exe ──UIA──► LiveCaptionsScraper.seed_baseline + poll_once(delta)
Whisper (file/live) ─────► LiveWhisperSession / transcribe_audio (lang auto|en|hi)
                └─────────► Capture “Live capture feed” (scroll + heartbeat status)
                └─────────► data/transcripts/*.txt → Parse → Generate
```

## Files

- `backend/transcripts/live_captions.py` — HWND/PID find, seed, heartbeat  
- `transcript-notes-studio/transcript_studio/gui.py` — Capture UI + feed  
- `transcript-notes-studio/transcript_studio/config.py` — Whisper defaults  
- `transcript-notes-studio/transcript_studio/whisper_client.py` — preset order  

## Acceptance

- Start capture with existing panel text → saved file has **no** pre-start dump.  
- Live feed appends each new segment; status shows segment count / quiet time.  
- Whisper language default = Auto (Hindi + English); `en` / `hi` optional.  
- Advanced knobs hidden until “Show advanced”.
