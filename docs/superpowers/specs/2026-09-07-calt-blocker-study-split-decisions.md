# CALT blocker + study split — combined decision doc

**Date:** 2026-09-07  
**Status:** Partially superseded (2026-09-07 evening)  
**Superseded for SoftLand-as-brain / product split by:** [2026-09-07-calt-productivity-cpp-product-design.md](./2026-09-07-calt-productivity-cpp-product-design.md)  
**Still valid:** SoftLand ON ≠ Arm naming; zero Python at kill time; Settings hub in `calt_focus`; P7 rejected; no CT code.

**Historical context:** Locked SoftLand *compute* on Python `:8000` and parked P5. Owner later locked **CALT Productivity (C++)** as owner of SoftLand decide, tracking runtime, day-pass/free/incubation, and hard-block — Study webapp = content only.

**Related:** [2026-09-07-one-engine-map.md](./2026-09-07-one-engine-map.md) (options map; product lock wins) · [softland-state-model](./2026-09-07-calt-productivity-softland-state-model.md)

---

## 1. One-sentence product shape

| Piece | Owns | Runs as |
|-------|------|---------|
| **CALT Study (content)** | Notes, Study Loop UI, Journal, GRE, Math, Bible pages, export | React + Python FastAPI `:8000` + SQLite |
| **CALT Productivity (blocker)** | SoftLand decide/apply, Arm, kill list, lock, day-pass/free/incubation, tracking, Settings/Focus | C++ (`calt_focus` + SoftLand engine + `calt_msg_host` + `calt_enforcer`) |
| **Hard block engine** | OS process kills, stay-alive, anti-tamper, sessions | `calt_enforcer.exe` (C++, zero Python at kill time) |
| **SoftLand site wire (target)** | Allow / interstitial / study-only | Gate → `calt_msg_host` → **C++ SoftLand** (not live `:8000`) |

**Study webapp = study content only.**  
**C++ Productivity = track + SoftLand + hard-block.**  
They may share files later for optional study events; SoftLand must not require uvicorn.

---

## 2. Decisions locked today

### D1 — SoftLand *compute* on Python `:8000` — **SUPERSEDED**
**Was:** Keep SoftLand decision logic in Python.  
**Now (product lock):** SoftLand decide + day-pass/free/incubation/goals-as-blocker-state live in **CALT Productivity (C++)**. Study content (Bible *pages*, Study Loop *UI*, notes) stays Python. See [product design](./2026-09-07-calt-productivity-cpp-product-design.md).

### D2 — Kills never require Python
`calt_enforcer` reads `enforcer_policy.json`, kills, writes `enforcer_status.json`.  
No live uvicorn needed for Arm / Disarm / kill loop. **Unchanged.**

### D3 — Settings live in the Focus shell, not a second product
- All blocker-facing settings live under Productivity **Settings** hub (`#focus`, `#policy`, `#rules`, …) and/or `/productivity/focus`.
  - `#rules` = App kill list CRUD + SoftLand site extras + gate schedules (Focus `#focus` Arms the saved kill list).
- `calt_focus.exe` (tray + WebView2) is the daily door to that UI.
- Study pages (notes, Study Loop, etc.) stay normal webapp routes; user can open them in browser or later from tray if useful.
- **No** Qt, **no** Python tray, **no** Electron.

### D4 — SoftLand vs Arm naming (forever)
| Name | Meaning |
|------|---------|
| `softland_enabled` (UI/API; DB may still say `hard_block_enabled`) | SoftLand / game-bank — **sites only**, no OS kills |
| `hard_block_armed` | Native kill switch in `enforcer_policy.json` only |

SoftLand ON does **not** kill Steam.  
Arm does **not** SoftLand sites by itself.

### D5 — Msg-host — **UPDATED by product lock**
- Gate talks to `calt_msg_host` via Native Messaging.
- Host asks **C++ SoftLand engine** (not Python) for mode — Productivity phases P3–P4.
- HTTP `:8000` fallback only during migration; then delete.
- Enforcer remains kill path; SoftLand state is separate store (Phase 2 model).

### D6 — Ranking — **UPDATED**
| ID | Meaning | Status |
|----|---------|--------|
| P0 (old) | Stay split SoftLand Python | **Superseded** by Productivity product |
| P1 | Strong OS engine | **Done** |
| P3 | One control door | **Done** |
| Prod P2–P4 | SoftLand state + native decide + drop `:8000` SoftLand | **Active roadmap** |
| P4 (old) | Msg-host → Python | **Superseded** |
| P5/P6 (old park) | Native SoftLand / monolith | **Un-parked as Prod P3–P6** |
| P7 | Python kills again | **Rejected** |

---

## 3. Where every setting lives

| Setting | UI home | Runtime owner |
|---------|---------|----------------|
| Arm / Disarm, kill list, lock, last kill | Settings `#focus` + `/productivity/focus` | `enforcer_policy.json` → `calt_enforcer` |
| SoftLand on, schedules, site rules, day-pass / free / incubation (blocker state) | Settings `#policy` / `#rules` → **C++ Productivity store** (Phase 2+) | See softland-state-model |
| SoftLand game-bank / categories / scores (legacy SoftLand labeling) | Settings `#policy` | Migrating; not OS kills |
| Planning / morning RO knobs | Settings `#planning` | Study/productivity UI; SoftLand-affecting bits move to Productivity store |
| Demo clock | Settings `#demo-mode` | Python |
| Wearables | Settings `#watch` | Python |
| Reminders | Settings `#reminders` | Client + planner |
| Scoring overrides | Settings `#scoring` | Python (study analytics) |
| Export | Settings `#export` | Python |
| Tracker setup docs | Settings `#setup` | Docs only |
| Study notes, GRE, Math, Journal, Study Loop UI | Normal webapp routes | **CALT Study** Python + React |

**Principle:** Blocker controls → Focus shell / Settings.  
Study content → webapp.  
Same login / same DB; different jobs.

---

## 4. Answered open questions

### Q: Should SoftLand keep calling Python `:8000`?
**No (product lock).** Near-term migration may keep HTTP fallback; target is Gate → `calt_msg_host` → C++ SoftLand with uvicorn optional/stopped. See [product design](./2026-09-07-calt-productivity-cpp-product-design.md).

### Q: Should “all settings” move into the native shell?
**Productivity / blocker settings: yes** (Focus shell / Settings).  
**Study content settings (notes structure, GRE prefs, etc.): no** — stay in Study webapp.

### Q: What is the webapp for?
**CALT Study** content only: notes, loops UI, planner pages, Bible reading, journal, GRE/Math.  
Not the SoftLand brain and not the kill engine.

### Q: What if Python is down?
| Feature | Behavior (target after Prod P3–P4) |
|---------|--------------------------------------|
| OS kills / Arm | Work (`calt_enforcer` + policy JSON) |
| SoftLand site decisions | Work (C++ SoftLand + msg-host) |
| Study pages | Down until API is back |

### Q: Extension ID for msg-host manifest?
Use **unpacked Gate ID** from `edge://extensions` day-to-day.  
`install_calt_msg_host.ps1` takes the ID as a parameter (or a small id file).  
Update when you package a fixed ID.

### Q: Tray default?
- Open Focus → `/productivity/focus` (keep).  
- Optional later: Open Settings → `?tab=settings#focus` (P3 polish).

---

## 5. Target wiring (after P1 + optional P4)

```text
YOU
  calt_focus.exe (tray + WebView2)
       → React Settings / Focus     (blocker controls)
       → React study routes         (notes, loops, …)  when you navigate there

SOFTLAND SITES
  Edge Gate
       → [today] HTTP :8000
       → [P4]    calt_msg_host → HTTP :8000   (same decision)
       → apply allow / interstitial

HARD BLOCK
  Settings Arm
       → enforcer_policy.json
       → calt_enforcer.exe → kills + status JSON

STUDY COMPUTE
  Python :8000 + SQLite
       → SoftLand answers, planner, Bible, scores, export, session ingest
```
