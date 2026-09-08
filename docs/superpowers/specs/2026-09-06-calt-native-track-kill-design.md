# CALT Native Track + Kill — Approach 1 (owner-approved)

**Date:** 2026-09-06  
**Status:** Approved — implement N3 then gap-check  
**Legal:** Cold Turkey = pattern only. No CT code.

## Decision

| Concern | Owner |
|---------|--------|
| Study webapp + SoftLand API + gate **compute** | **Python FastAPI** (keep) |
| Tracker **control UI** | **React** `/productivity/focus` (not PySide6) |
| OS kills + boot stay-alive | **C++** `calt_enforcer` |
| Foreground sessions → SQLite | **C++** (N3) |
| Incubation / reward ledger | **Python API** — web Focus calls it |

## Shared DB

- File: `data/vocab_app.db`
- Kills: `enforcer_runtime` (Python writes, C++ reads)
- Sessions: `tracked_sessions` (C++ inserts when service running; `source=desktop_tracker`, `category_source=native`)

## Ownership lock

`data/behavior/enforcer_owner.lock` — C++ heartbeat. When active:

- Python skips **kills**
- Python skips **session persist** (enqueue/persist)
- Python still refreshes gate / incubation / Dashboard

## Success

1. Close Desktop UI → kills continue (service)
2. Sessions appear in Dashboard / day status from native writes
3. Extension SoftLand still via `:8000`
4. `run.bat` study stack unchanged
