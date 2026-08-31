# CALT Voice (T-Rex 3)

Black-screen voice notes for Amazfit T-Rex 3 / Zepp OS 5.

## Behavior

1. Open **CALT Voice** (app list or shortcut card) → recording **starts immediately**
2. **Near-black screen** — tap anywhere to stop
3. **Vibrate** on start and when saved
4. Auto-stops at **5:00**
5. If free disk **&lt; 1 GB** → shows error, does **not** record

## Recording indicator

While recording, a small dot below centre steps through dim red shades on a 2s
cycle, with elapsed `MM:SS` under it in dark grey. Both go black when recording stops.

Clips save as Opus under the app data folder (`data://voice_….opus`).

## Sending clips to the PC

Swipe **left** from the recorder (only when not recording) to open **Files**.
Tap a clip to send. Clips land in `data/voice_notes/` on the PC.

Sending is manual on purpose: recording never waits on Bluetooth.

**It is slow.** Audio goes over the BLE message channel (~1 KB per round trip), so a long clip can take several minutes. Keep watch and phone awake. Progress shows as `192.168.0.110 41/583`.

Opening **Files** pings the hub first: `Receiver up: …` or `No receiver: …`. After a failed send, tap the clip again to retry (resume skips chunks already held).

## PC setup (same for CALT Sync)

1. Start the **desktop tracker** (hub on `:8765`).
2. Find the PC LAN IP (`ipconfig` — e.g. `192.168.0.110`).
3. Phone Zepp app → **CALT Voice** settings:
   - **Base URL:** `http://<PC-LAN-IP>:8765`
   - **Fallback URL:** optional always-on host with the same voice-note routes
   - **Ingest token:** `calt-local-wearables`
4. Verify in the **phone browser:** `http://<PC-LAN-IP>:8765/health`
5. Same Wi‑Fi; never `localhost`.

## Where a clip can live

| State | Meaning |
|---|---|
| **On watch** | Listed in Files — `3 on watch · 1.4MB` |
| **Confirmed at receiver** | Re-hashed and accepted; watch copy deleted — footer `last → <host>` |

**The phone cannot store clips** — side service has Messaging, Fetch, Settings only; no filesystem read API. See README section in repo for full rationale.

With no fallback URL, clips stay on the watch until the PC is back.

## Integrity

| Step | Guarantee |
|---|---|
| `VN_BEGIN` | Declares size + FNV-1a hash; returns resume indices + pinned receiver |
| `VN_CHUNK` | Per-chunk hash; fixed offset writes |
| `VN_FINISH` | Whole-file re-hash before publish |
| Delete | Only after `VN_FINISH` reports `stored` |

Hub routes (wearable key required):

```text
POST /api/hub/voice-note/begin | /chunk | /finish
GET  /api/hub/voice-note/status?upload_id=… | /list
```

Backend: `tests/test_voice_notes.py`. FNV-1a in `page/notes.js` must match `backend/behavior/voice_notes.py`.

**Web app download:** after a clip lands on the PC, open **Productivity → Watch ↔ PC → CALT Voice clips** and click **Download** (same files in `data/voice_notes/`).

## Install

```bat
packages\calt-voice\sideload.bat
```

Requires **mic** permission — reinstall after updates. Add the **Voice** shortcut card for one-tap access.

**Not verified on hardware** — no emulator for BLE chunk relay; backend protocol is pytest-covered.

## SDK notes

- `@zos/media` recorder needs **API_LEVEL ≥ 3.0** (target **4.0** for T-Rex 3)
- Zeus CLI: `npm i -g @zeppos/zeus-cli@latest`
