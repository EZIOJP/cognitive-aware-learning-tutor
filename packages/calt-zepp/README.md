# CALT Sync 4.1 — manual health dumper (Zepp OS 6)

Watch app that **dumps body metrics** to the desktop tracker hub. No plans, calendar, notifications, or PC remote.

Watch stamps **calendar day + timezone offset** before BLE. Phone must not replace that with its own clock.

## What it does

| Action | Behavior |
|--------|----------|
| **Dump today** | Capture full body snapshot into a 7-day local queue |
| **Send queue** | POST queued days oldest-first (chunked), with live progress + red errors |
| **Preview** | Shows sleep / steps / HR / SpO₂ / stress / temp (or n/a) |

## Install

Uninstall old CALT Sync first, then sideload **4.1.0**.

```bat
packages\calt-zepp\sideload.bat
```

## Phone settings

1. Desktop tracker running (`:8765`)
2. Base URL: `http://<PC-LAN-IP>:8765`
3. Token: `calt-local-wearables`
4. Open `http://<IP>:8765/health` in phone browser

## Metrics captured (when sensor exists)

Sleep, HR (+ downsampled today series), resting HR, stress (+ week if API), SpO₂, steps, calories, distance, PAI, stand, fat burn, sitting, battery, temperature **only if firmware exposes it**.

## Hub endpoint

```text
POST /api/wearables/zepp
GET  /api/wearables/zepp/health
```
