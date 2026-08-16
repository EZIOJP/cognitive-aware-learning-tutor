# CALT Voice (T-Rex 3)

Black-screen voice notes for Amazfit T-Rex 3 / Zepp OS 5.

## Behavior

1. Open **CALT Voice** (app list or shortcut card) → recording **starts immediately**
2. **Black screen** — tap anywhere to stop (no timer / labels while recording)
3. **Vibrate** on start and when saved
4. Auto-stops at **5:00**
5. If free disk **&lt; 1 GB** → shows error, does **not** record

Clips save as Opus under the app data folder (`data://voice_….opus`). Pull them via Zepp / file tools later if needed.

## Install

```bat
packages\calt-voice\sideload.bat
```

Requires **mic** permission — reinstall after updates so Zepp prompts again. If it fails, the screen shows a short error (e.g. `Mic: …`).

Add the **Voice** shortcut card from the watch’s widget / shortcut settings for one-tap access.

## SDK notes

- `@zos/media` recorder needs **API_LEVEL ≥ 3.0** (we target **4.0** for T-Rex 3 / OS 5)
- `app.json` permissions include `device:os.mic`, `media`, `record`
- Zeus CLI: keep `@zeppos/zeus-cli` current (`npm i -g @zeppos/zeus-cli@latest`)

## Notes

Recording while staying on the stock watch face is **not** supported by Zepp OS Mini Programs. Black full-screen UI is the intentional trade-off.
