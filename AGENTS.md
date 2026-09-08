# Agent Context

You are finishing a **local-first study + productivity platform** for daily personal use.

**Mandate (2026-09-07 — owner locked):** **Two products.**

| Product | Tech | Owns |
|---------|------|------|
| **CALT Productivity** | C++ (`calt_enforcer` + SoftLand engine + tracker + `calt_msg_host` + `calt_focus`) | Tracking, SoftLand decide/apply, hard-block kills/locks, schedules, day-pass/free/incubation, goals-as-blocker-state, productivity Settings/Focus UI, tray |
| **CALT Study** | Python FastAPI + React `:8000` | Notes, Study Loop *content*, GRE, Math, Journal, Bible *content* — pure study workflows |

- SoftLand must **not** depend on live `:8000` (target: Gate → msg-host → C++ SoftLand).  
- Study may optionally emit events into the productivity store later; Study is **never** the SoftLand brain.  
- **Cold Turkey** = language/architecture *pattern* only — **no CT code**.  

```text
DESKTOP TRACKER RULE (locked):
calt_enforcer.exe must start, read policy, kill processes, write sessions,
hold the ownership lock, and expose status with ZERO runtime dependency
on any Python process.

PRODUCTIVITY RULE (locked 2026-09-07):
SoftLand decide, day-pass/free/incubation accounting, and productivity
tracking runtime belong to the C++ Productivity product — not the study
webapp. Python may remain for study content only.
```

**Authoritative product lock:** [docs/superpowers/specs/2026-09-07-calt-productivity-cpp-product-design.md](docs/superpowers/specs/2026-09-07-calt-productivity-cpp-product-design.md)  
**Phase 2 SoftLand store:** [docs/superpowers/specs/2026-09-07-calt-productivity-softland-state-model.md](docs/superpowers/specs/2026-09-07-calt-productivity-softland-state-model.md)  
**Prior split (partially superseded for SoftLand-as-brain):** [docs/superpowers/specs/2026-09-07-calt-blocker-study-split-decisions.md](docs/superpowers/specs/2026-09-07-calt-blocker-study-split-decisions.md)  
**One-engine map (options; SoftLand-on-Python brain superseded):** [docs/superpowers/specs/2026-09-07-one-engine-map.md](docs/superpowers/specs/2026-09-07-one-engine-map.md)  
**P5a (superseded by Productivity product lock):** [docs/superpowers/specs/2026-09-07-p5a-native-softland-study-flags-design.md](docs/superpowers/specs/2026-09-07-p5a-native-softland-study-flags-design.md)  
Design: [docs/superpowers/specs/2026-09-06-calt-native-enforcer-design.md](docs/superpowers/specs/2026-09-06-calt-native-enforcer-design.md)  
Plan: [docs/superpowers/plans/2026-09-06-calt-native-enforcer.md](docs/superpowers/plans/2026-09-06-calt-native-enforcer.md)

Quiz mandate is **Done** (regressions only). EEG soft-fail is **Done** (flash needs USB).

---

## Architecture (locked)

```text
CALT Study (content only)     → Python + React (:8000) — notes, GRE, quiz UI, Bible pages
CALT Productivity (blocker)   → C++ product:
  SoftLand decide/apply       → SoftLand engine + calt_msg_host (Gate native messaging)
  OS kills + stay-alive       → calt_enforcer (ZERO Python)
  Tracking                    → native (expand browser path over phases)
  Settings / Focus UI         → calt_focus (tray + WebView2)
Policy kills hot path         → data/behavior/enforcer_policy.json (mirror)
SoftLand state (SoT)          → SQLite productivity_* in data/vocab_app.db
Writes (only mutator)         → calt_enforcer gateway: \\.\pipe\calt_enforcer_cmd
SoftLand hot read             → data/behavior/softland_policy.json (mirror)
Status (native-owned)         → data/behavior/enforcer_status.json
```

**Naming (forever):** `softland_enabled` = sites / SoftLand only. `hard_block_armed` = native kill switch only. SoftLand ON ≠ Arm.

**Owner (2026-09-07):** Desktop **app + UI is essential** via **`calt_focus.exe`**
(CT-class split: tray UI ≠ kill engine). WebView2 hosts React **Productivity**
(Calendar / Plan / Settings / Focus) — study content stays in the Study webapp.
Prefer **prebuilt `dist-focus/`** (`npm run build:focus`, virtual host `calt.app`).
No Qt, no pystray, no Electron.
`run_calt_desktop.bat` launches `calt_focus.exe`. PySide6 `calt_desktop` remains **legacy only**
(`run_calt_desktop_qt.bat`).

---

## Current focus

| Phase | Deliverable | Status |
|-------|-------------|--------|
| N1–N3 | Native kills + sessions | **Done** |
| Z0–Z4 | Enforcer JSON path / Focus Arm / publish | **Done** |
| P0 (old) | Stay split SoftLand Python / kills native | **Superseded** by Productivity product lock |
| P1 | Strong OS engine (browsers, anti-tamper, Admin scripts) | **Done** (owner: run Admin install once if not already) |
| P3 | One control door (tray → Settings) | **Done** (`Open Settings` → `?tab=settings`) |
| **Prod P0** | Product lock: Productivity C++ vs Study Python | **Done** (this doc + product design) |
| **Prod P2** | C++-owned SoftLand **state** store + UI writes | **Done** (softland_policy.json writers/migrator) |
| **Prod P3** | Gate → msg-host → native SoftLand decide | **Done** (`calt_msg_host` get_mode; Gate nativeMessaging + HTTP fallback) |
| **Prod P4** | Remove SoftLand HTTP `:8000` dependency | **Done** (Gate HTTP SoftLand fallback opt-in only; edits go through the gateway) |
| **Prod P5** | Native unlock accounting + classification/scoring (owner chose full P5 2026-09-08) | **Designed, not built** — [P5 design](docs/superpowers/specs/2026-09-08-calt-productivity-p5-native-unlock-accounting-design.md); first plan ready: [P5a](docs/superpowers/plans/2026-09-08-calt-productivity-p5a-native-unlock-accounting.md) |
| **Prod P6** | Browser track without Python | Planned |
| **Phase 2 gateway** | Enforcer-owned command API + SQLite SoT + SoftLand tick; JSON mirrors | **Backend done + verified with `:8000` stopped** (2026-09-08). Next: Settings **frontend** overhaul only |
| P4 (old) | Msg-host relay → Python | **Superseded** — host must ask C++ SoftLand, not Python |
| P7 | Python kills again | **Rejected** |

**Parked ideas (not product lock):** [docs/superpowers/exports/2026-09-07-ct-maturity-ideas-reminder.md](docs/superpowers/exports/2026-09-07-ct-maturity-ideas-reminder.md) — Tier 1 **done**. Tier 2+ ideas only; no CT code.

**Morning smoke:** [docs/superpowers/exports/2026-09-07-morning-smoke.md](docs/superpowers/exports/2026-09-07-morning-smoke.md)

**How the rules actually behave (read before Settings work):** [docs/BLOCKING_RULES.md](docs/BLOCKING_RULES.md)

---

## How to work

1. Anchor this file + [Productivity C++ product design](docs/superpowers/specs/2026-09-07-calt-productivity-cpp-product-design.md)  
2. Wire, don’t migrate study **content**; SoftLand/blocker state moves to C++-owned store per Phase 2 model  
3. No CT code  
4. Commits only when user asks  
5. Python `enforcer_service` = **legacy fallback only** — do not add new Python kill/track code  
6. Never require a live Python process for `calt_enforcer` to arm/kill/track/status  
7. SoftLand decide: Gate → `calt_msg_host` → C++ `get_mode`. The HTTP `:8000` SoftLand fallback is off unless `caltSoftlandHttpFallback` is set (debug only). 
8. SoftLand SoT = **SQLite `productivity_*` tables in `data/vocab_app.db`**, mutated only by the `calt_enforcer` gateway (named pipe `\\.\pipe\calt_enforcer_cmd`); `softland_policy.json` / `enforcer_policy.json` are published **mirrors**. Python may still write the JSON mirror — the enforcer imports it when its `updated_at` is newer. SoftLand never sets `hard_block_armed`. 

## Dev

```bat
run.bat
python -m alembic upgrade head
scripts\desktop_tracker\build\build_native_enforcer.bat
powershell -File scripts\desktop_tracker\install\install_native_enforcer.ps1
scripts\desktop_tracker\build\build_calt_msg_host.bat
powershell -File scripts\desktop_tracker\install\install_calt_msg_host.ps1 -ExtensionId <GATE_ID>
:: verify the native path with no Python running
powershell -File scripts\desktop_tracker\run\gateway_cmd.ps1 -Op status.snapshot
powershell -File scripts\desktop_tracker\run\msg_host_cmd.ps1 -Json "{\"type\":\"get_mode\",\"url\":\"https://youtube.com\"}"
```

Thin compat shims still exist at the old flat paths under `scripts\desktop_tracker\` (e.g. `build_native_enforcer.bat` → `build\…`). Prefer the `build\` / `install\` / `run\` / `installer\` layout; see `scripts\desktop_tracker\README.md`.
