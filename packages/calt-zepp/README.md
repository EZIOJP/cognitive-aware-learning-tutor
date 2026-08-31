# CALT Sync 4.1 — manual health dumper (Zepp OS 6)

Watch app that **dumps body metrics** to the desktop tracker hub. No plans, calendar, notifications, or PC remote.

Watch stamps **calendar day + timezone offset** before BLE. Phone must not replace that with its own clock.

## What it does

| Action | Behavior |
|--------|----------|
| **Dump today** | Capture full body snapshot into the local queue |
| **Send queue** | Fill forward from the last synced day to today, oldest-first (chunked), with live progress + red errors |
| **Test PC** | Settings → Test PC pings hub health via phone |
| **Preview** | Shows sleep / steps / HR / SpO₂ / stress / temp (or n/a) |

## Fill-forward sync

Send walks the queue oldest-first, so each run fills from the **last fully-synced
day** up to today. A day is marked synced — and the watermark advances — only
after **all four chunks** are ACKed by the server, so an interrupted send resumes
at the failed chunk rather than skipping the day.

The status line reads `Pending N · thru YYYY-MM-DD`, or `Up to date · thru …`.

**Retention.** A day the server has accepted is dropped after 7 days. A day that
was **never delivered** is kept for **30** (`UNSENT_KEEP_DAYS`), so a few weeks
away from the PC cannot silently delete undelivered health data.

**Gaps cannot be backfilled.** The watch sensor APIs only report the *current*
day — there is no historical query. If the app never ran on a given day, that day
has no snapshot and no later sync can reconstruct it. Send reports these as
`Nd never captured` rather than claiming a clean fill. To avoid gaps, dump daily
(the shortcut card makes this one tap).

**Replay is safe.** Every chunk carries a stable `dump_id`/`chunk_id`; the server
records them in `wearable_ingest_event` and no-ops on repeats, and merges compare
`captured_at` so a stale chunk cannot overwrite newer values.

## PC setup (same for CALT Voice)

1. Start the **desktop tracker** (hub listens on `:8765` by default).
2. Find the PC LAN IP (`ipconfig` on Windows — e.g. `192.168.0.110`).
3. Phone Zepp app → **CALT Sync** settings:
   - **Base URL:** `http://<PC-LAN-IP>:8765`
   - **Ingest token:** `calt-local-wearables`
4. Verify in the **phone browser:** `http://<PC-LAN-IP>:8765/health` → `{"ok":true,...}`
5. Watch and phone on the **same Wi‑Fi**. Do **not** use `localhost`.

## Install

Uninstall old CALT Sync first, then sideload **4.1.3**.

```bat
packages\calt-zepp\sideload.bat
```

On watch: **Dump today** → **Send queue**. On failure, tap **Send queue** again (resumes chunk). Settings → **Test PC** checks reachability without sending health data.

**Web app:** after ingest, open **Productivity → Watch ↔ PC → CALT Sync health dump** on `http://localhost:5173` (main API `:8000`) to see the latest dump status and metrics.

## Metrics captured (when sensor exists)

Sleep, HR (+ downsampled today series), resting HR, stress (+ week if API), SpO₂, steps, calories, distance, PAI, stand, fat burn, sitting, battery, temperature **only if firmware exposes it**.

## Hub endpoints

```text
POST /api/wearables/zepp
GET  /api/wearables/zepp/health
```

Auth headers (phone side service): `Authorization: Bearer <token>` and `X-CALT-Wearable-Key: <token>`.

## Limitations

- **Not verified on hardware** in CI — BLE relay + sensor APIs need a real T-Rex 3.
- Transfers are **slow** over BLE; keep watch + phone awake during Send.
- **No historical days** — only days you dumped exist in the queue.
