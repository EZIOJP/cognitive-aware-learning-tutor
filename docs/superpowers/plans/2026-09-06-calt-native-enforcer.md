# CALT Native Enforcer (C++) — Implementation Plan

> **For agentic workers:** Execute N1→N2. No Cold Turkey code.

**Design:** [2026-09-06-calt-native-enforcer-design.md](../specs/2026-09-06-calt-native-enforcer-design.md)

## Task N1 — Schema + Python publisher

- [x] Alembic `0034_enforcer_runtime`
- [x] Model + `publish_enforcer_runtime(db, user_id, gate, policy)`
- [x] Call from `compute_distraction_gate` / tracker gate refresh
- [x] Tests

## Task N2 — C++ service skeleton

- [x] `native/calt_enforcer/` CMake project
- [x] SQLite read of `enforcer_runtime` + kill by exe name
- [x] Ownership lock file write
- [x] Console mode + Windows Service entry
- [x] `scripts/desktop_tracker/build_native_enforcer.bat`
- [x] `scripts/desktop_tracker/install_native_enforcer.ps1`

## Task N3 — Handoff

- [x] Prefer native binary in install docs
- [x] Python `enforcer_service` = fallback only
- [x] Update AGENTS.md / SETUP

## Verify (evidence)

- `alembic current` → `0034_enforcer_runtime`
- `pytest tests/test_enforcer_runtime_publish.py` → pass
- `build_native_enforcer.bat` → `calt_enforcer.exe`
- Service install requires Admin (owner machine): `install_native_enforcer.ps1`
