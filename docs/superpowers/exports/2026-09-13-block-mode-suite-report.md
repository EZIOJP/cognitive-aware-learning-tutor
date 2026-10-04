# SoftLand / Arm comprehensive block-mode suite

**When:** 2026-09-13 ~14:13 IST  
**Result:** **73 PASS / 0 FAIL / 0 SKIP**  
**Gateway:** recovered (restarted wedged `calt_enforcer --console`) then ok  
**Snapshot restored:** yes (SoftLand OFF; Arm disarmed; `exes: []`; `lock_mode: none`; unlock password retained)

Scripts:
- `scripts/desktop_tracker/run/block_mode_suite.py` — orchestrator
- `scripts/desktop_tracker/test_fixtures/` — disposable Arm EXEs
- Prior one-shots: `_arm_state_dump.py`, `_block_mode_report.py`

Machine-readable: `docs/superpowers/exports/2026-09-13-block-mode-suite-results.json`

---

## How to run

```bat
rem Safe: SoftLand fixture matrix + Arm match unit + sync (no live kills)
python scripts\desktop_tracker\run\block_mode_suite.py

rem Live SoftLand probes + Arm fixture kills; snapshots/restores SoftLand+Arm
python scripts\desktop_tracker\run\block_mode_suite.py --live --arm-kills

rem Rebuild disposable Arm EXEs (needs clang)
scripts\desktop_tracker\test_fixtures\build_fixtures.bat
```

---

## Matrix coverage

| Axis | Result |
|------|--------|
| SoftLand ON / OFF | PASS (fixture) |
| STUDY / FREE / INCUBATION | PASS (fixture) |
| porn / watch / block_extra / allow / not_listed | PASS |
| www / subdomain / http / path noise / localhost / IP / empty URL | PASS |
| SoftLand OFF → all allow | PASS |
| FREE → watch open, porn + block_extra still blocked | PASS |
| Arm match unit (case, basename, path token, protected exes) | PASS |
| Arm ON → fixture target killed; safe EXE untouched | PASS (live) |
| Arm OFF → listed fixture not killed | PASS (live, after fix) |
| SQLite vs JSON Arm sync | PASS post-fix (was FAIL pre-fix) |
| SoftLand live (owner SoftLand OFF) | PASS — all `softland_off` |

---

## Code fixes shipped this pass

1. **Password disarm sticky re-arm (misfire)** — `arm.set` left `lock_mode=password` after a valid unlock disarm; `ApplyStickyLock` forced Arm back ON next tick, so “Disarm” still killed listed apps. Fix: when writing `hard_block_armed=false`, clear `lock_mode` to `none` (keep unlock secret for next Arm). Focus UI now sends `lock_mode: "none"` on disarm.
2. **SQLite `enforcer_runtime` stale vs JSON** — `arm.set` wrote JSON only; SQLite kept an old game list. Added `SyncEnforcerRuntimeSqlite` on Arm publish so mirrors match (JSON remains authoritative at load).
3. **Suite process check** — `tasklist` truncates long EXE names; live Arm assertions now use `Get-Process`.

---

## Residual risks / owner follow-ups

1. **Kill list empty after restore** — Pre-test JSON already had `exes: []` (SQLite still listed Steam/etc. but JSON wins). Runtime was already not killing games. Re-add apps in Focus → Blocker / Arm if you want kills again, and set password lock if desired (`unlock_password` is still stored).
2. **Gateway pipe can wedge** — Suite may restart `calt_enforcer --console` when SoftLand is OFF. Prefer Task Scheduler / service install for stay-alive.
3. **`strict_allowlist` does not block unlisted hosts** — `github.com` / random hosts stay `not_listed` allow in STUDY (by design in `softland_decide.cpp`).
4. **Device hosts porn block** — not exercised by this suite (separate from SoftLand heuristic).
5. **Enforcer binary** — rebuilt and copied to `scripts/desktop_tracker/installer/installer_payload/bin/calt_enforcer.exe`; console instance was restarted for tests.

---

## Product reminder

SoftLand ON ≠ Arm. SoftLand blocks sites; Arm kills processes.
