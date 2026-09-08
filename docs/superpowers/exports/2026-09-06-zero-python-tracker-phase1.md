# Zero-Python desktop tracker — Phase 0+1

**Date:** 2026-09-06  
**Mandate:** DESKTOP TRACKER RULE in `AGENTS.md` + `native/calt_enforcer/README.md`

## Done (Phase 1)

| Item | Change |
|------|--------|
| Policy | `policy_db.cpp` reads SQLite + overlays `data/behavior/enforcer_policy.json` |
| Loop | Poll ~1.5s; kill when armed+locked/incubation |
| Status | Writes `data/behavior/enforcer_status.json` every ~2.5s |
| Lock | Unchanged refresh |
| Sessions | Unchanged (browsers skipped) |

## Not yet (Phase 2+)

- Stop Python `enforcer_runtime_publish` / status probe / backfill on Focus path
- React Focus reads `enforcer_status.json` directly
- Focus writes `enforcer_policy.json` (Phase 3A)

## Smoke (owner)

```bat
taskkill /F /IM python.exe /T
taskkill /F /IM pythonw.exe /T
copy data\behavior\enforcer_policy.json.example data\behavior\enforcer_policy.json
scripts\desktop_tracker\build_native_enforcer.bat
scripts\desktop_tracker\run_native_enforcer_console.bat
```
