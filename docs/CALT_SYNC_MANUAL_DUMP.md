# CALT Sync 4.0 — Manual Health Dumper

**Date:** 2026-08-15  
**Package:** `packages/calt-zepp` **4.0.0** (appId `1088801`)  
**Supersedes for watch UX:** planner/calendar/notify/remote parts of `2026-07-20-calt-sync-v3-design.md`

## Model

Watch = dumb manual dumper. PC = smart scraper (validate, merge, dedupe).

| Watch | Backend |
|-------|---------|
| Dump today → 7-day local queue | Field-aware merge into `wearable_daily` |
| Send queue oldest-first, chunked HTTP | Idempotent `wearable_ingest_event` |
| No plans / calendar / notify / PC remote | Life Tracker + hub readings with stable `client_event_id` |

## Constraints

- Zepp does not support reliable persistent WebSockets → queued HTTP POSTs.
- “7-day dump” = flush days the app already captured. Sensors do not invent history.
- Temperature only if firmware exposes it; never fabricate zeroes.
- Oversize payloads are **rejected** (413), never truncated.

## Install

```bat
packages\calt-zepp\sideload.bat
```

Uninstall older CALT Sync first. Phone Base URL = tracker hub `http://<PC-LAN-IP>:8765`.

## Migration

```bat
python -m alembic upgrade head
```

Adds `wearable_ingest_event` + replay columns on `wearable_daily` (`0028_wearable_ingest_replay`).

## Verify

```bat
python -m pytest tests/test_wearable_ingest_merge.py tests/test_wearables_zepp.py -q
```
