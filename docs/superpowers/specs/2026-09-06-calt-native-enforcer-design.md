# CALT Native Enforcer — design (study-first)

**Date:** 2026-09-06  
**Status:** Owner-approved  
**Legal:** Cold Turkey is **UX/architecture reference only**. No CT source, binaries, DBs, or cloned proprietary logic.

## Decision (final)

| Concern | Owner |
|---------|--------|
| Study stack (quiz, notes, planner, Bible, gate **policy compute**) | **Python** FastAPI + SQLite |
| Web app + Desktop WebView Dashboard | **Python/JS** (read/write same DB via API) |
| OS hard-block **process kills** + boot stay-alive | **C++ Windows service** |
| Browser SoftLand | **CALT Gate extension** (still polls Python `:8000`) |
| Session productivity tracking (foreground → minutes) | **Stays Python for now** (phase 2 can move to C++ events → same DB) |

**Shared database:** `data/vocab_app.db` (same file Python already uses). C++ opens it **read-mostly** for enforcement; Python remains the writer for study data and for a small `enforcer_runtime` snapshot row.

## Why not “drop all Python tracking tonight”

Full session tracking + SoftLand + planner in C++ would rewrite half the product. Owner priority is **native OS kills like CT**, while keeping **study-first** Python DB/API. That is this design.

## Data contract (same SQLite)

### Existing (Python writes, C++ may read)

- `productivity_policies` — `hard_block_enabled`, `hard_block_exes` (JSON), `hard_block_gaming`, `daily_goal_minutes`, `user_id`

### New table `enforcer_runtime` (Python writes on gate refresh; C++ reads)

| Column | Meaning |
|--------|---------|
| user_id | Solo owner id |
| hard_block_armed | Mirror of policy |
| gate_locked | Distraction gate locked |
| incubation_active | Force kills during incubation |
| exes_json | JSON array of exe names to kill |
| updated_at | UTC |

C++ **does not** reimplement morning/Bible/plan logic — it trusts this snapshot + policy.

## Process model (CT-like roles, CALT code)

```text
[CALT Desktop · Focus Web UI] → settings via Python API → SQLite
[CALT Gate extension]         → SoftLand via Python :8000
[C++ CALTEnforcer service]    → read SQLite → TerminateProcess on listed exes
[Python TrackerService]       → session logging only; SKIP kills when native owns
```

Ownership file `data/behavior/enforcer_owner.lock` is written by the **C++ service** so Python UI does not double-kill.

### CT vs CALT (roles + code)

**Yes for enforcement shape:** native service owns kills / stay-alive; UI is only control; rules live in a local DB the service reads.  
**No for “everything identical”:** CALT keeps a **study-first Python stack** (webapp, planner, SoftLand API, gate compute). That is intentional — not a CT clone. Session tracking stays Python until N3.

| Piece | Cold Turkey–like | CALT now | CALT code |
|-------|------------------|----------|-----------|
| Kill apps / stay alive | Native Windows service | C++ `calt_enforcer` | `native/calt_enforcer/` · install `scripts/desktop_tracker/install_native_enforcer.ps1` |
| Edit rules / dashboard | Native UI | Web Dashboard + Desktop | `backend/behavior/calt_desktop/dashboard/` · `widgets/webview_dashboard.py` · Focus tabs |
| Where rules / kill snapshot live | CT’s own DB | Shared SQLite `data/vocab_app.db` | table `enforcer_runtime` · model `backend/models/enforcer_runtime.py` · publish `backend/behavior/enforcer_runtime_publish.py` · Alembic `0034` |
| Who computes study / gate / SoftLand JSON | CT block engine | **Python** (planner, incubation, gate) | `backend/behavior/distraction_gate.py` · `browser_gate_policy.py` · FastAPI `:8000` |
| Session “what was I on” | Built into CT app | Python tracker (N3 → C++ later) | `backend/behavior/tracker_service.py` (skips kills when `enforcer_owns_kills`) |
| Browser SoftLand | CT website block | CALT Gate → `:8000` | `calt-gate-extension/` |
| Study webapp (quiz, notes, Bible, …) | *(not CT)* | **CALT-only** React + FastAPI | `src/` · `backend/` · `run.bat` |
| Fallback if native missing | — | Python enforcer | `backend/behavior/enforcer_service/` |

## Build / install

- `native/calt_enforcer/` — CMake + MSVC (or clang-cl)
- Install as Windows Service `CALTEnforcer` (auto-start)
- Fallback: existing Python enforcer only if native binary missing

## Phases

| Phase | Deliverable |
|-------|-------------|
| **N1** | C++ service: read `enforcer_runtime` + kill exes; claim ownership lock |
| **N2** | Python publishes `enforcer_runtime` from gate compute; install scripts |
| **N3** | (Later) C++ foreground tracking → insert/update tracked sessions in same DB |
| **N4** | (Later) Optional native messaging bridge for extension |

## Success

- Closing Desktop UI does not stop kills (C++ service running)
- Arm/disarm + exe list still edited in Desktop / policy (Python → DB)
- Extension SoftLand unchanged
- `run.bat` study stack unchanged
- No Cold Turkey code in tree
