# CALT Sync 4.2 — rich health dumper (Zepp OS 6)

Watch app that dumps **rich body metrics** to the PC. Posts to the **tracker hub**
(`:8765`) first, then auto-falls back to the **FastAPI backend** (`:8000`) on the
same LAN IP — so Sync works even when only `run.bat` is up.

Watch stamps **calendar day + timezone offset** before BLE. Phone must not replace that with its own clock.

## What it does

| Action | Behavior |
|--------|----------|
| **Dump today** | Capture full body snapshot into the local queue |
| **Dump & Send** | Capture then flush queue in one tap |
| **Send queue** | Upload queued days (hub → API fallback) |
| **Test PC** | Settings → Test PC pings hub/API health |

## Rich payload (`processed_v2`)

When sensors exist: sleep (+ stages / light / rem / naps), HR (+ downsampled today series, max/avg), resting HR, stress (+ hour/week), SpO₂ (+ recent), steps, calories, distance, PAI, stand, fat burn, sitting, battery, temperature, **workouts**, **HR zones**, weather/device meta.

Chunks (5): Sleep · Activity · Heart · Series · Extras — resume-safe, idempotent.

## PC setup

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

Uninstall older CALT Sync first, then sideload **4.2.0**.

## Hub / API

```text
POST /api/wearables/zepp
GET  /api/wearables/zepp/health
GET  /api/wearables/zepp/status   → categories inventory
```

Same routes on hub and FastAPI. Auth: `Authorization: Bearer <token>` + `X-CALT-Wearable-Key`.

## Limits

- No historical days the app never dumped
- BLE transfers are slow — keep watch + phone awake during Send
- Workout history only if firmware exposes `Workout` API
