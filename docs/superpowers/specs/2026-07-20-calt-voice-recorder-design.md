# CALT Voice — T-Rex 3 black-screen recorder

**Date:** 2026-07-20  
**Status:** Implemented (v1)  
**Package:** `packages/calt-voice` (appId `1088803`)

## Goal

One-tap voice notes on Amazfit T-Rex 3 (Zepp OS 5):

1. Open app (list or shortcut card) → **auto-start** recording  
2. **Black screen only** while recording (no timer) · tap to stop  
3. Vibrate on **start** and **end**  
4. Auto-stop at **5 minutes**  
5. **Never start** if free disk space &lt; **1 GB**

## Non-goals

- Record while staying on the stock watch face (OS cannot)  
- Upload / transcription (later)  
- Background App Service mic (playback-only APIs in service; unreliable)

## UX

```text
Open → space check
  fail → red text "Need 1GB free" (no vibe / no mic)
  ok   → vibe → black UI → REC mm:ss → tap Stop
Stop / 5:00 → stop file → vibe → "Saved" → reopen to record again
```

Files: `data://voice_YYYYMMDD_HHMMSS.opus`

## Shortcut

App-widget / shortcut card opens `page/index` (still opens app; black screen is intentional).
