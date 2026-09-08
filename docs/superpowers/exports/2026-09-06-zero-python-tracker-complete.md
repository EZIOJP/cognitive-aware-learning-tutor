# Zero-Python desktop tracker — COMPLETE

**Date:** 2026-09-06 / 2026-09-07  
**Rule:** `calt_enforcer` runs with ZERO Python. Web API may only drop/read policy JSON.

## Final shape

```text
Focus Arm/Disarm  →  PUT /api/behavior/enforcer-policy  →  enforcer_policy.json
Gate SoftLand     →  publish_enforcer_runtime           →  enforcer_policy.json (JSON only)
calt_enforcer.exe →  reads policy JSON, kills, tracks, writes enforcer_status.json
Focus status      →  reads enforcer_status.json (via thin API helper)
```

No SQLite `enforcer_runtime` mirror. No Focus category backfill. No Python kill/track loop.

## Agent done

| Item | Status |
|------|--------|
| Phase 0 mandate | Done |
| Phase 1 native self-sufficient | Done |
| Phase 2 status/policy JSON path | Done |
| Phase 3A Focus Arm/Disarm | Done |
| Publish JSON-only | Done |
| Focus backfill removed | Done |

## Owner smoke (you)

Full: [2026-09-07-morning-smoke.md](./2026-09-07-morning-smoke.md)

```bat
scripts\desktop_tracker\run_native_enforcer_console.bat
REM Focus → Arm hard block (notepad.exe) → open Notepad → dies
REM Optional: taskkill python → enforcer still kills
powershell -File scripts\desktop_tracker\install_native_enforcer.ps1
```

## Maturity (2026-09-07)

Tier 1 done: broad browsers, anti-tamper, msg-host ping, strong locks, service-prefer launchers.  
Next: Tier 2 — see [ct-maturity-ideas-reminder.md](./2026-09-07-ct-maturity-ideas-reminder.md).
