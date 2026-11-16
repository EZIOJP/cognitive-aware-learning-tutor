# CALT Sync 4.3 — rich health dumper (Zepp OS 6)

Watch app that dumps **rich body metrics** to the PC. Posts to the **Focus / tracker hub**
(`:8765`) first, then falls back to Study FastAPI (`:8000`) if configured.

Watch stamps **calendar day + timezone offset** before BLE. Phone must not replace that with its own clock.

## What it does

| Action | Behavior |
|--------|----------|
| **Sync** | One circular button — dump today + flush queue to Focus hub |
| **Ping PC** | Connectivity test — hub writes `wearables_ping.json` + Windows tray toast |
| **Auto sync** | Watch Settings → ON · alarm every 1/3/6/12h → Sync |
| **Test PC** | Settings → same as Ping PC (health + notify) |

## Rich payload (`processed_v2`)

When sensors exist: sleep (+ stages / light / rem / naps), HR (+ downsampled today series, max/avg), resting HR, stress (+ hour/week), SpO₂ (+ recent), steps, calories, distance, PAI, stand, fat burn, sitting, battery, temperature, **workouts**, **HR zones**, weather/device meta.

Chunks (5): Sleep · Activity · Heart · Series · Extras — resume-safe, idempotent.

## PC setup

### Focus (recommended for Productivity)

1. Run `calt-focus\scripts\run\start_wearables_hub.bat` (`:8765`).
2. Phone Zepp → **CALT Sync** settings:
   - **Base URL:** `http://<PC-LAN-IP>:8765`
   - **API URL:** leave blank (Focus has no Study `:8000`)
   - **Ingest token:** `calt-local-wearables`
3. Phone browser: `http://<IP>:8765/health`

### Study (legacy dual stack)

1. Prefer **desktop tracker** (hub `:8765`) **or** API only (`run.bat` `:8000`).
2. Phone Zepp → **CALT Sync** settings:
   - **Base URL:** `http://<PC-LAN-IP>:8765`
   - **API URL:** leave blank (auto `http://<same-IP>:8000`) or set explicitly
   - **Ingest token:** `calt-local-wearables`
3. Phone browser: `http://<IP>:8765/health` and/or `http://<IP>:8000/health`

## Install

```bat
packages\calt-zepp\sideload.bat
```

Uninstall older CALT Sync first, then sideload **4.3.0**. Turn on **Auto sync** in watch Settings after the first successful Dump & Send.

## Hub / API

```text
POST /api/wearables/zepp          → ingest (Focus coerces + mirrors; stores wearable_raw/)
POST /api/wearables/zepp/raw      → raw dump; Focus does all processing
POST /api/wearables/zepp/ping     → connectivity ping → PC toast + wearables_ping.json
GET  /api/wearables/zepp/health
GET  /api/wearables/zepp/status   → categories inventory + last_ping
```

Same routes on hub and FastAPI. Auth: `Authorization: Bearer <token>` + `X-CALT-Wearable-Key`.

## Limits

- No historical days the app never dumped
- BLE transfers are slow — keep watch + phone awake during Send
- Workout history only if firmware exposes `Workout` API
