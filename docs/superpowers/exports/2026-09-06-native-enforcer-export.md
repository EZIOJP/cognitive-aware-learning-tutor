# CALT native enforcer + desktop tracker — export pack (complete pass)

**Date:** 2026-09-06  
**Legal:** CALT original only. No Cold Turkey binaries/code.

## Done this pass (agent)

| Change | Path |
|--------|------|
| Edge = Microsoft Edge + active tab | `browser_labels.py`, SelfTracker `v1.5.27`, `tracker_bridge.py`, `stats_aggregate.py` |
| Extension Edge kept in stats | `tracker_ignore.py` (`source=extension`) |
| Native skips browsers (no double-count) | `native/calt_enforcer/src/session_db.cpp` |
| Native rebuild + Inno payload copy | `build_native_enforcer.bat` → `installer_payload/bin/` |
| **F5** Installer bundles native + Register helpers | `install_calt_desktop.iss` `0.2.1-v2d-native`, `compile_installer.bat` |
| Task Scheduler prefers native | `install_enforcer_service.ps1` |
| Admin service helper | `installer_payload/Register Native Enforcer.bat` |
| Category backfill on Focus + desktop-stats | `native_session_backfill.py` via `dashboard_bridge` + `router` |
| Backend readme export | `2026-09-06-desktop-tracker-backend-export.md` |

## Owner still does (cannot automate without Admin / Inno)

| ID | Action |
|----|--------|
| **F1** | Admin: `powershell -File scripts\desktop_tracker\install_native_enforcer.ps1` |
| **Inno** | Install [Inno Setup 6](https://jrsoftware.org/isinfo.php) then `scripts\desktop_tracker\compile_installer.bat` |
| **Edge** | Reload SelfTracker + Gate in `edge://extensions` |
| **API** | Keep `run.bat` up for SoftLand + Focus |

## How to run now

```bat
scripts\desktop_tracker\build_native_enforcer.bat
powershell -ExecutionPolicy Bypass -File scripts\desktop_tracker\install_enforcer_service.ps1 -Start
scripts\desktop_tracker\run_calt_desktop.bat
REM Admin (boot-class service):
powershell -File scripts\desktop_tracker\install_native_enforcer.ps1
```

## Related

- Backend map: `docs/superpowers/exports/2026-09-06-desktop-tracker-backend-export.md`
- Suggestions JSON: `suggested_further_changes.json`
