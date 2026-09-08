# Gap checklist — native track + kill + Desktop (2026-09-06)

Run through after install. Fix gaps only when the system is otherwise working.

## Migrations / DB

- [x] Alembic head `0034_enforcer_runtime`
- [x] Table `enforcer_runtime` exists
- [x] Table `tracked_sessions` exists (unchanged schema)
- [x] Gate refresh publishes row (Focus / distraction-gate while `:8000` up)

## Native binary

- [x] `build_native_enforcer.bat` → `calt_enforcer.exe` (+ copy to Inno payload)
- [x] N3 session writer compiled in (browsers skipped — SelfTracker owns tabs)
- [x] No-admin Task Scheduler: `install_enforcer_service.ps1 -Start` (native preferred)
- [ ] Admin: `install_native_enforcer.ps1` → Windows Service `CALTEnforcer` (owner UAC)
- [ ] Close Focus UI → kills still happen when armed+locked
- [ ] After app switch ≥2s → new `tracked_sessions` row with `category_source=native`

## Python handoff

- [x] `enforcer_owns_kills` / `enforcer_owns_tracking`
- [x] Tracker skips kills + SQLite persist when lock fresh
- [x] Gate compute + SoftLand stay on Python `:8000`
- [x] Desktop frontend = Web Focus `/productivity/focus` (not C++ UI)
- [x] Edge active-tab → `msedge.exe` + sites in desktop-stats
- [x] Native category backfill on Focus + desktop-stats

## Study webapp

- [ ] `run.bat` still serves quiz/notes/Bible (owner smoke)
- [ ] Extension SoftLand still polls `:8000` (reload SelfTracker + Gate)

## Installer

- [x] Inno script `0.2.1-v2d-native` bundles exe when present
- [ ] Owner: install Inno Setup 6 → `compile_installer.bat`

## Known follow-ups

- See [2026-09-06-calt-session-tracking-gaps.md](./2026-09-06-calt-session-tracking-gaps.md)
- Incubation still driven by Python break_reward ledger
- MSVC Build Tools optional (MinGW build OK)
- **Do not** copy Cold Turkey files — patterns only
