# CALT Desktop Tracker — Architecture Export

**Date:** 2026-09-06  
**Audience:** Read this for “how the whole board fits together.”  
**Legal:** CALT original. Cold Turkey = pattern language only — **no CT code**.  
**Pack index:** [2026-09-06-calt-desktop-tracker-README.md](./2026-09-06-calt-desktop-tracker-README.md)

---

## 1. Mandate (locked)

| Layer | Technology | Owns |
|-------|------------|------|
| Study webapp + gate **policy** | Python FastAPI + SQLite | SoftLand JSON, categories, Focus APIs, planner |
| Browser SoftLand | `calt-gate-extension` → `:8000` | Redirect / block sites |
| Active **tab** time | `selftracker-extension` | Edge URL/domain → `tracked_sessions` |
| OS **kills** + non-browser FG | C++ `calt_enforcer` | Process kills; `tracked_sessions` without browsers |
| Control UI | React `/productivity/focus` | Arm/status/PIN/earned — **not** PySide6 |

Shared DB: `data/vocab_app.db`  
Ownership lock: `data/behavior/enforcer_owner.lock`

---

## 2. System diagram

```text
                    ┌─────────────────────────────────────────┐
                    │         React SPA (Vite)                │
                    │  /productivity/focus   ← control UI     │
                    │  /productivity         ← calendar+stats │
                    │  Sidebar: Study|Focus|Life|System       │
                    └───────────────┬─────────────────────────┘
                                    │ HTTP JWT
                                    ▼
┌──────────────┐          ┌───────────────────────────────────┐
│ CALT Gate    │ SoftLand │  FastAPI :8000                    │
│ extension    │─────────►│  distraction_gate                 │
└──────────────┘          │  enforcer_runtime_publish ──────┐ │
                          │  tracker_bridge (SESSION_END)   │ │
┌──────────────┐          │  stats_aggregate / desktop-stats│ │
│ SelfTracker  │ WS/HTTP  │  focus-dashboard                │ │
│ (Edge tabs)  │─────────►│                                 │ │
└──────────────┘          └───────────────┬─────────────────┘ │
                                          │ same SQLite       │
                                          ▼                   │
                          ┌───────────────────────────────┐   │
                          │ data/vocab_app.db             │◄──┘
                          │  tracked_sessions             │
                          │  enforcer_runtime             │
                          │  productivity_policies        │
                          └───────────────┬───────────────┘
                                          │ reads kill list
                                          │ writes non-browser sessions
                                          ▼
                          ┌───────────────────────────────┐
                          │ calt_enforcer.exe (C++)        │
                          │  kills + session_db           │
                          │  skips browsers (Edge etc.)   │
                          └───────────────────────────────┘
```

---

## 3. Data ownership matrix

| Data | Writer | Reader |
|------|--------|--------|
| Gate SoftLand / mode | Python `distraction_gate` | Gate extension, Focus UI |
| `enforcer_runtime` (exes to kill) | Python publish | C++ enforcer |
| Edge tab sessions | SelfTracker → `ingest_behavior_session` | stats / Productivity |
| App FG sessions (non-browser) | C++ `session_db` | stats (category backfill by Python) |
| Ownership lock | C++ (refresh) | Python skips kills/persist when fresh |
| Focus snapshot | `dashboard_bridge` | Focus React panel |

---

## 4. Session sources (`tracked_sessions.source`)

| `source` | Meaning |
|----------|---------|
| `extension` | SelfTracker active tab (Edge = `msedge.exe` + site in title) |
| `desktop_tracker` | Native or Python desktop FG (browsers ignored at capture/stats for bare Edge) |
| `calt_spa` | Study presence on local CALT SPA |

**Edge rule:** extension owns browsing time; native **skips** browser FG; desktop ignore keeps bare `msedge.exe` out of stats unless `source=extension`.

---

## 5. Control vs enforce (Phase 1+)

```text
Focus UI / Productivity UI     =  control + visibility (web)
Python SoftLand compute        =  browser SoftLand only (extensions → :8000)
Native calt_enforcer           =  hard OS kills + non-browser track + status JSON
                                 ZERO Python required at runtime
Policy                         =  SQLite enforcer_runtime and/or enforcer_policy.json
Status                         =  data/behavior/enforcer_status.json (native writes)
```

Closing the browser Focus page does **not** stop kills if the Task Scheduler / Windows Service is running.

See: [zero-python-tracker-phase1.md](./2026-09-06-zero-python-tracker-phase1.md)

---

## 6. Feature IA (web shell)

Sidebar section bars (not usage-app categories):

| Bar | Features |
|-----|----------|
| Study | Notes, Study Loop, Journal, GRE, Math, Study Room |
| Focus | Focus control, Calendar |
| Life | Bible, Life Tracker, Nutrition |
| System | Home, Settings, Admin |

Focus page sections: **Now → Actions → Enforcer → Related**

Code: `src/layout/navSections.ts`, `AppSidebar.tsx`, `FocusControlPanel.tsx`

---

## 7. Runtime paths

| Path | Role |
|------|------|
| `run.bat` | API + Vite |
| `scripts/desktop_tracker/run_calt_desktop.bat` | Open Focus + native console if built |
| `install_enforcer_service.ps1` | Logon Task Scheduler (native preferred) |
| `install_native_enforcer.ps1` | Admin Windows Service |
| `build_native_enforcer.bat` | Build C++ + Inno payload copy |

---

## 8. Related exports

| Doc | Depth |
|-----|--------|
| [backend-export](./2026-09-06-desktop-tracker-backend-export.md) | APIs, ingest, DB columns |
| [frontend-export](./2026-09-06-desktop-tracker-frontend-export.md) | React routes, Focus, extensions |
| [native-export](./2026-09-06-desktop-tracker-native-export.md) | C++ files + install |
| [overview](./2026-09-06-calt-desktop-tracker-overview.md) | Owner how-to |
| [file-manifest.json](./2026-09-06-desktop-tracker-file-manifest.json) | Path inventory |
| Specs | `docs/superpowers/specs/2026-09-06-calt-native-enforcer-design.md` |
| AGENTS.md | Locked mandate |

---

## 9. One sentence

**Python computes policy and stores sessions; SelfTracker times Edge tabs; C++ kills apps and tracks the rest; React Focus is the control UI on one SQLite database.**
