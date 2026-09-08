# CALT Desktop Tracker v2 — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Date:** 2026-09-06  
**Status:** §0 locked · Tasks 1–7 implemented (2026-09-06) — **manual QA + commits pending owner**  
**Goal:** Cold Turkey–like installable CALT Desktop Focus app: readable Dashboard, Windows service enforcer, incubation breaks + earned free-time ledger — all on the **existing** gate/policy brain.  
**Architecture:** [docs/superpowers/specs/2026-09-06-calt-desktop-tracker-v2-design.md](../specs/2026-09-06-calt-desktop-tracker-v2-design.md) (superseded for decisions by this plan)  
**Suggested path:** `docs/superpowers/plans/2026-09-06-calt-desktop-tracker-v2.md`

---

## 0. Remaining questions — **LOCKED** (`§0 defaults OK`, 2026-09-06)

Owner accepted recommended defaults. Freeze these for v2c wiring.

### Q1 — What ends a “focused study block” and starts an incubation break?

- [x] **A4** Mix: planner study block end **or** productive streak ≥ N min *(N=45)*  

**Answer:** **A4** (N=45)

### Q2 — What credits the earned free-time ledger?

- [x] **B5** Configurable weights for B1–B4  

**Answer:** **B5** — Bible, plan confirm, daily goal, Study Loop (weights in config)

### Q3 — During incubation, what does enforcement do?

- [x] **C2** Force browser/study-hard mode for the break duration (no entertainment SoftLand)  

**Answer:** **C2**

### Q4 — PIN free override during incubation?

- [x] **D1** PIN **cannot** start or extend free override while incubation is active  

**Answer:** **D1**

### Q5 — Earned free time spend path?

- [x] **E1** Spend ledger minutes → existing `set_free_override(minutes=…)` + PIN  

**Answer:** **E1**

### Q6 — Incubation defaults (tunable config)?

**Answer:** **defaults OK** — work **45** min → break **8** min; max 1 incubation per hour; no snooze

### Q7 — Ledger earn rates (starting caps)?

**Answer:** **defaults OK** — Bible **+15**; plan confirm **+10**; daily goal **+30**; daily earn cap **60**; spend via PIN

### Q8 — Assumed product defaults still OK?

| # | Locked / assumed | Keep? |
|---|------------------|-------|
| D2 | U2 WebView2 Dashboard + Qt editors | **Y** |
| D4 | V1 thin Windows service | **Y** |
| D5 | P2 Inno installer | **Y** |
| D6 | W1 web calendar unchanged | **Y** |
| D7 | M1 morning gate explained only | **Y** |
| D8 | E1 extension on `:8000` | **Y** |
| D9 | Name CALT Desktop · Focus | **Y** |

**Answer:** **all Y**

### Q9 — Build start order?

- [x] Start **v2a** immediately; freeze Q1–Q7 before **v2c**  

**Answer:** Start **v2a** now

---

## 1. Locked decisions

| # | Decision | Answer |
|---|----------|--------|
| D1 | Scope | **S3** — dashboard + Windows-service enforcer + named-block/break/reward config on **existing** gate. No new block DB, no rewrite. |
| D2 | UI shell | **U2** *(assumed)* — PySide6 for Rules/Schedules/Device/Bible/Plan/Watch/Voice; WebView2 Dashboard for status + break/reward UX |
| D3 | More time | **T3** — incubation + earned free-time ledger (§3); old “PIN-only display” plan replaced |
| D4 | Windows service | **V1** *(assumed)* — thin service: boot, hard-block kills, restart-on-crash; reads existing policy |
| D5 | Installer | **P2** *(assumed)* — Inno Setup (or similar): Start Menu, optional autostart, uninstall |
| D6 | Web | **W1** *(assumed)* — `/productivity` calendar stays; banner “managed in Desktop” |
| D7 | Morning | **M1** *(assumed)* — Dashboard explains, does not replace |
| D8 | Extension | **E1** *(assumed)* — keep FastAPI `:8000` |
| D9 | Name | **CALT Desktop** *(assumed)*, subtitle **Focus** |
| D10 | Order | v2a → v2b → **v2c** (break/reward) → v2d installer |

---

## 2. Why S3, not a rewrite

Full CT rewrite (S4) = second block database + engine that ignores today’s gate. S3 keeps **one policy brain** (`browser_gate_policy` / `distraction_gate` / productivity policy) and adds incubation + ledger on top.

**Legal:** Cold Turkey is reference UX only — no CT code, DBs, or binaries.

---

## 3. Break / reward system (core mechanic)

### 3a. Incubation breaks — mandatory, entertainment-free

- After focused study (see Q1), auto-start incubation  
- Games / video / social / leisure browse stay blocked  
- UI: plain countdown, walk/stretch copy, or lock-style screen  
- Duration short (Q6); **PIN does not skip** (Q4)  
- Purpose: diffuse-mode rest — deliberately boring  

### 3b. Earned free time — scarce reward

- Credits from completed study/morning goals (Q2 / Q7)  
- Only path that unlocks entertainment; spend via existing PIN + `set_free_override` (Q5)  
- Caps in config, not hardcoded  

### 3c. Everything else

- Unchanged `browser_gate_policy` / `distraction_gate` / morning / schedules / device hosts  

---

## 4. Data model (additive only)

New Alembic revision (next after current head, e.g. `0033_…`):

**`break_sessions`**

| Column | Type | Notes |
|--------|------|--------|
| id | int PK | |
| user_id | int | |
| kind | str | `incubation` \| `earned` |
| started_at | datetime UTC | |
| duration_sec | int | |
| ended_at | datetime nullable | |
| source_session_id | str nullable | planner block id / tracker session / quiz id |
| payload_json | text | `{}` |

**`reward_ledger`**

| Column | Type | Notes |
|--------|------|--------|
| id | int PK | |
| user_id | int | |
| delta_minutes | int | +earn / −spend |
| reason | str | `bible_done`, `plan_confirm`, `daily_goal`, `spend_free`, … |
| created_at | datetime UTC | |
| ref_id | str nullable | |
| balance_after | int | denormalized running balance |

No changes to events/entities/feature_registry.

Config file (JSON): `data/behavior/break_reward_config.json` — work/break minutes, earn rates, daily cap.

---

## 5. Phased delivery

| Phase | Deliverable | Done when |
|-------|-------------|-----------|
| **v2a** | WebView2 Dashboard: active / why / until + incubation countdown UI (can be stub-triggered) | Owner sees what’s blocked without logs |
| **v2b** | Windows service enforcer: hard-block kills, autostart, restart-on-crash | Closing UI does not stop kills |
| **v2c** | Incubation scheduler + reward ledger wired to real study/morning events | Study focus → mandatory break; goal → ledger credit; spend → PIN free time |
| **v2d** | Inno installer | Double-click install, Start Menu, no terminal |

---

## 6. File map (repo reality)

| Path | Role |
|------|------|
| `backend/behavior/calt_desktop/` | Existing Desktop app |
| `backend/behavior/calt_desktop/dashboard/` **new** | HTML/CSS/JS for WebView2 Dashboard |
| `backend/behavior/calt_desktop/dashboard_bridge.py` **new** | JSON API for Dashboard (status, ledger, break state) |
| `backend/behavior/calt_desktop/widgets/webview_dashboard.py` **new** | `QWebEngineView` / WebView2 host tab |
| `backend/behavior/calt_desktop/main_window.py` | Add Dashboard as first tab |
| `backend/behavior/break_reward.py` **new** | Incubation scheduler + ledger earn/spend |
| `backend/behavior/browser_gate_policy.py` | Block PIN during incubation; honor forced study mode during break |
| `backend/behavior/distraction_gate.py` | Expose break/ledger summary fields on gate payload |
| `backend/behavior/tracker_service.py` | Optional hooks: focus streak / block end → break_reward |
| `backend/behavior/enforcer_service/` **new** | Windows service entry (v2b) |
| `backend/models/break_reward.py` **new** | SQLAlchemy models |
| `alembic/versions/0033_break_reward.py` **new** | Migration |
| `scripts/desktop_tracker/install_calt_desktop.iss` **new** | Inno (v2d) |
| `tests/test_break_reward.py` **new** | Unit tests |
| `calt-gate-extension/` | Unchanged (still `:8000`) |

---

## 7. Components

| Unit | Responsibility | Depends on |
|------|----------------|------------|
| Dashboard HTML | Status + incubation countdown + earned balance + spend CTA | Bridge JSON only |
| Bridge | Gate snapshot + break state + ledger R/W | `distraction_gate`, `break_reward`, PIN dialogs |
| Qt editors | Rules / Schedules / Device / … | Existing tabs |
| Enforcer service | Kills + stay-alive; fire/enforce incubation windows | Policy + `break_reward` state |
| Installer | Ship app + optional WebView2 bootstrapper + service | Artifacts |
| FastAPI | Study + gate HTTP for extension | Existing |

### Bridge JSON shape (v2a minimum)

```json
{
  "active": {
    "hard_block_armed": true,
    "browser_mode_label": "Study",
    "morning_next": "bible",
    "why": "Finish today's Bible chapter to unlock the plan.",
    "until": { "kind": "morning", "label": "Until Bible is done" },
    "blocked_summary": ["Games & listed apps", "Leisure sites (SoftLand)", "Device porn hosts on"]
  },
  "incubation": { "active": false, "remaining_sec": 0, "total_sec": 480 },
  "earned": { "balance_minutes": 0, "daily_earned": 0, "daily_cap": 60 },
  "actions": {
    "can_spend_earned": false,
    "can_pin_free": true,
    "incubation_blocks_pin": false
  }
}
```

---

## 8. Risks

| Risk | Mitigation |
|------|------------|
| WebView2 missing | Installer Evergreen bootstrapper; Qt fallback panel |
| Incubation feels punitive | Conservative defaults (Q6); tune via config |
| Ledger too stingy | Visible balance; rates in JSON (Q7) |
| Service + UI race | Service owns kills/timers; UI owns settings; one DB |
| Scope → CT clone | S4 rejected; no CT code |

---

## 9. Success criteria

- [ ] Dashboard: active / why / until in plain English  
- [ ] Incubation auto-triggers and PIN cannot bypass  
- [ ] Earned balance visible and tied to real completions  
- [ ] Closing UI does not stop hard-block (post v2b)  
- [ ] Installed app launches without terminal (post v2d)  
- [ ] `run.bat` / `:8000` + extension unchanged  

---

## 10. Implementation tasks

### Task 0: Freeze §0 answers

- [x] Owner fills §0 or replies `§0 defaults OK`  
- [x] Update this plan’s Q answers inline  
- [ ] Commit plan (when owner asks for commits)

---

### Task 1: v2a — Dashboard bridge + HTML (no service yet)

**Files:**
- Create: `backend/behavior/calt_desktop/dashboard_bridge.py`
- Create: `backend/behavior/calt_desktop/dashboard/index.html` (+ minimal css/js)
- Create: `backend/behavior/calt_desktop/widgets/webview_dashboard.py`
- Modify: `backend/behavior/calt_desktop/main_window.py`
- Create: `tests/test_dashboard_bridge.py`

- [x] Write failing test: `snapshot_for_user(user_id)` returns `active.why` string and `blocked_summary` list from a stub gate  
- [x] Implement `snapshot_for_user` reading `compute_distraction_gate` + policy (plain-language helpers)  
- [x] Add WebView (or `QTextBrowser` fallback) tab **Dashboard** as first tab  
- [x] Load local `dashboard/index.html`; poll bridge every 5–10s  
- [x] Stub incubation panel (hidden unless `incubation.active`)  
- [ ] Manual: launch Desktop → Dashboard shows mode / why / until  
- [ ] Commit when asked  

---

### Task 2: v2a — Wire Free time / Rules CTAs from Dashboard

- [x] Bridge action endpoints / Qt slots: open Rules, Schedules, Device, Free-time PIN dialog (existing)  
- [x] Disable PIN CTA in UI when `actions.incubation_blocks_pin` (prep for v2c)  
- [ ] Manual click-through  
- [ ] Commit when asked  

---

### Task 3: v2b — Enforcer service skeleton

**Files:**
- Create: `backend/behavior/enforcer_service/__main__.py`
- Create: `backend/behavior/enforcer_service/service.py`
- Create: `scripts/desktop_tracker/install_enforcer_service.ps1` (dev)  
- Modify: docs in `docs/SETUP_AND_COMMANDS.md` (when implementing)

- [x] Service loop: load gate → `should_hard_block` → kill (reuse tracker kill helpers)  
- [x] Restart-on-crash via Task Scheduler or service recovery  
- [x] Desktop UI no longer required for kills when service running  
- [ ] Test: start service, close UI, launch blocked exe → still killed  
- [ ] Commit when asked  

---

### Task 4: v2c — Migration + models

- [x] Alembic `0033_break_reward` + `backend/models/break_reward.py`  
- [x] Register models; update `docs/MIGRATIONS.md`  
- [x] Config JSON loader with Q6/Q7 defaults  
- [x] Tests for migrate + empty ledger balance 0  
- [ ] Commit when asked  

---

### Task 5: v2c — `break_reward` module

- [x] `start_incubation` / `tick_incubation` / `incubation_active`  
- [x] `earn(user_id, reason, minutes)` / `spend(user_id, minutes)` → balance  
- [x] Gate hooks: deny `set_free_override` while incubation active  
- [x] Unit tests for earn/spend/cap and PIN denial  
- [ ] Commit when asked  

---

### Task 6: v2c — Triggers from real study events

- [x] Hook focus-end (per Q1) → `start_incubation`  
- [x] Hook Bible done / plan confirm / daily goal (per Q2) → `earn`  
- [x] Dashboard shows live countdown + balance  
- [x] Spend → PIN → `set_free_override` + ledger debit  
- [ ] Manual acceptance: study → incubation; goal → credit; spend → free browse  
- [ ] Commit when asked  

---

### Task 7: v2d — Installer

- [x] Inno script: app files, Start Menu, optional autostart, WebView2 bootstrapper note  
- [x] Document uninstall / service removal  
- [ ] Smoke install on clean path  
- [ ] Commit when asked  

---

## 11. Out of scope

- Cold Turkey code or cloned break engines beyond §3  
- Second policy brain / new block DB  
- Extension rewrite / SoftLand in Desktop  
- Full web calendar inside Desktop  
- Android Device Gate  

---

## 12. Next step

1. Owner answers **§0** (or `§0 defaults OK`).  
2. Agent executes **Task 1** (v2a Dashboard) via subagent-driven development.  
3. After v2a works, continue Task 2→7 in order.
