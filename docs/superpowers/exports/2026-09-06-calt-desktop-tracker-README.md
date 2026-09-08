# CALT Desktop Tracker — Export Pack Index

**Date:** 2026-09-06 (updated)  
**Product:** CALT Desktop · Focus (desktop tracker stack)  
**Legal:** CALT original only. Cold Turkey = architecture *pattern* only — **no CT code**.

Read in this order:

| # | File | Contents |
|---|------|----------|
| 0 | **[architecture-export](./2026-09-06-desktop-tracker-architecture-export.md)** | **System diagram, ownership matrix, data flows** |
| 0b | [zero-python-tracker-complete](./2026-09-06-zero-python-tracker-complete.md) | **Phases 0–3A done** — JSON policy/status, Focus Arm |
| 0c | [ct-maturity-ideas-reminder](./2026-09-07-ct-maturity-ideas-reminder.md) | Tier 1 **done**; Tier 2–3 ideas |
| 0d | **[morning-smoke](./2026-09-07-morning-smoke.md)** | Wake-up smoke test commands |
| 0e | [morning-status](./2026-09-07-morning-status.md) | Overnight polish summary |
| 0f | **[owner-tasks](./2026-09-07-owner-tasks.md)** | Your checklist + QoL done |
| 1 | [overview](./2026-09-06-calt-desktop-tracker-overview.md) | Owner how-to (run, install, checklist) |
| 2 | [backend-export](./2026-09-06-desktop-tracker-backend-export.md) | **Backend** — DB, ingest, APIs, Edge tabs |
| 3 | [frontend-export](./2026-09-06-desktop-tracker-frontend-export.md) | **Frontend** — Focus, Calendar, sidebar IA, extensions |
| 4 | [native-export](./2026-09-06-desktop-tracker-native-export.md) | C++ enforcer + install scripts |
| 5 | [file-manifest.json](./2026-09-06-desktop-tracker-file-manifest.json) | Machine-readable path list |
| 6 | [native-enforcer status](./2026-09-06-native-enforcer-export.md) | F1–F5 done / owner leftovers |
| 7 | [suggested_further_changes.json](./suggested_further_changes.json) | Suggestions JSON |

## Architecture (one glance)

```text
React Focus + Calendar     →  control / stats UI
Python FastAPI + SQLite    →  policy, SoftLand, ingest, stats
SelfTracker (Edge)         →  active-tab sessions
calt_enforcer (C++)        →  OS kills + non-browser sessions
```

## Quick start

```bat
run.bat
scripts\desktop_tracker\build_native_enforcer.bat
powershell -ExecutionPolicy Bypass -File scripts\desktop_tracker\install_enforcer_service.ps1 -Start
scripts\desktop_tracker\run_calt_desktop.bat
```

Then reload SelfTracker + Gate in `edge://extensions`.
