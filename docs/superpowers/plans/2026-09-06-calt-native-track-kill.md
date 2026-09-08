# Plan: Native track + kill integration (N3)

**Spec:** [2026-09-06-calt-native-track-kill-design.md](../specs/2026-09-06-calt-native-track-kill-design.md)

## Task 1 — C++ foreground + session write

- Add `foreground.cpp/h`, `session_db.cpp/h`
- Poll FG window; on switch ≥2s write `tracked_sessions`
- Wire into `RunEnforcerLoop` / service loop
- Rebuild `calt_enforcer.exe`

## Task 2 — Python skip persist when native owns

- `enforcer_owns_tracking()` (= ownership lock, same as kills)
- `flush_current` / recovery: skip enqueue/persist when owned
- Keep gate + incubation ticks

## Task 3 — Docs + gap checklist

- Update AGENTS.md N3 status
- SETUP note: native tracks + kills
- Smoke: alembic head, publish table, build exe, ownership helper
