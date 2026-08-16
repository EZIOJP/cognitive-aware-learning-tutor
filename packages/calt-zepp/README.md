# CALT Sync 4.0 — manual health dumper

Watch app that **dumps body metrics** to the desktop tracker hub. No plans, calendar, notifications, or PC remote.

## What it does

| Action | Behavior |
|--------|----------|
| **Dump today** | Capture full body snapshot into a 7-day local queue |
| **Send queue** | POST queued days oldest-first (chunked), delete day after ACK |
| **Preview** | Shows sleep / steps / HR / SpO₂ / stress / temp (or n/a) |

**7-day queue** = days you previously dumped on this watch. Sensors are mostly today-only; the app does not invent historical HR/sleep.

## Removed in 4.0

Notifications, background hourly capture, plans pull, calendar, day-status, Focus, Lock/Shutdown PC.

## Install

```bat
packages\calt-zepp\sideload.bat
```

Uninstall old CALT Sync first, then install **4.0.0**.

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
