# CALT Sync 4.1 — Manual Health Dumper (Zepp OS 6)

**Date:** 2026-08-18  
**Package:** `packages/calt-zepp` **4.1.0** (appId `1088801`)  
**OS:** Zepp OS 6 (API_LEVEL target 4.0, compatible 3.0)

## How watch ↔ phone sync works

Zepp has no always-on socket. Official path:

```text
Watch Device App  --BLE MessageBuilder (small JSON chunks)-->
Phone Zepp Side Service  --fetch() HTTP-->
CALT tracker hub :8765  --preprocess/postprocess-->
wearable_daily + Life Tracker
```

| Stage | What |
|-------|------|
| **Preprocess (watch)** | Stamp `local_date`, `tz_offset_min`, `captured_at` from the watch clock |
| **BLE** | 4 small chunks (Sleep / Activity / Heart / Extras), ACK per chunk |
| **Phone** | HTTP POST only — no busy-wait, no extra health ping per chunk |
| **Postprocess (PC)** | Keep the watch calendar day; convert `start_min`/`end_min` using `tz_offset_min` |

## Model

Watch = dump + queue. PC = merge, dedupe, sleep windows.

## Install

```bat
packages\calt-zepp\sideload.bat
```

Uninstall older CALT Sync first. Phone Base URL = `http://<PC-LAN-IP>:8765`.

## Verify

```bat
python -m pytest tests/test_watch_day_stamp.py tests/test_wearable_ingest_merge.py tests/test_wearables_zepp.py -q
```
