# CALT Sync v2 — calendar-first watch hub

**Date:** 2026-07-18  
**Status:** Building  
**Package:** `packages/calt-zepp` (separate from Adaptive Focus)

## Goal

Upgrade CALT Sync into a calendar-first companion:

1. **Calendar event sync** — planner blocks as day agenda on watch (+ reminders); open system Calendar when useful  
2. Morning auto-sync (sleep → Life Tracker)  
3. Today glance (sleep / stress / steps / next block / soft-day chip)  
4. Plan actions: Start / Done / Snooze 15m  
5. Reliability (host hints, last-good URL, retry)  
6. Quiet hourly stress/steps snapshot  
7. Launch Adaptive Focus (`appId` 1088802)

## Constraint

Zepp Mini Programs **cannot write** system Calendar events. “Calendar sync” = **CALT planner ↔ watch agenda UI + alarms/notifications**, plus optional `launchApp(SYSTEM_APP_CALENDAR)`.

## Backend

- `GET /api/wearables/zepp/calendar?days=2`  
- `POST /api/wearables/zepp/plans/{id}/start|complete|snooze`  
- Plans response includes `soft_day` / `load_scale` from wearable sleep
