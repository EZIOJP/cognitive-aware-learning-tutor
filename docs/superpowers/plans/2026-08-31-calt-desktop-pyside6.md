# CALT Desktop (PySide6) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship a single-process PySide6 desktop app that owns productivity rules, bible/morning plan, watch sync, and voice notes — while the website keeps only the productivity calendar (+ study stack).

**Architecture:** One `pythonw -m backend.behavior.calt_desktop` process runs `QApplication` + `QSystemTrayIcon` + existing `TrackerService` + hub `:8765`. Tabs call the same DB/modules/APIs as today’s React panels. Tk popups are replaced gradually; old `desktop_tracker` tray remains fallback until Phase 0 is stable.

**Tech Stack:** PySide6, existing FastAPI/SQLite gate modules, tracker_hub, voice_notes.

**Spec:** [docs/superpowers/specs/2026-08-31-calt-desktop-pyside6-design.md](../specs/2026-08-31-calt-desktop-pyside6-design.md)

**Restore point:** git tag `restore/pre-calt-desktop-pyside6` @ `5297c83`

## Global Constraints

- Windows-first; OCR lane untouched
- Do not remove productivity **calendar** from the website in v1
- One process (no Electron sidecar)
- Reuse `TrackerService`, `distraction_gate`, `browser_gate_policy`, `voice_notes`, hub — do not rewrite engines
- Minimal diffs; match existing naming under `backend/behavior/`
- Commits after each completed phase when owner asked for frequent checkpoints

## File map

| Path | Responsibility |
|------|----------------|
| `backend/behavior/calt_desktop/__main__.py` | Entry |
| `backend/behavior/calt_desktop/app.py` | QApplication bootstrap, start/stop TrackerService |
| `backend/behavior/calt_desktop/main_window.py` | Tabbed MainWindow shell |
| `backend/behavior/calt_desktop/tray.py` | QSystemTrayIcon menu |
| `backend/behavior/calt_desktop/tabs/*.py` | Today, Bible, Plan, Rules, Schedules, Device, Watch, Voice, Settings |
| `backend/behavior/calt_desktop/dialogs.py` | Hard-block / free-time PIN (Qt) |
| `scripts/desktop_tracker/run_calt_desktop.bat` | Launch |
| `tests/test_calt_desktop_smoke.py` | Import + optional offscreen smoke |
| `backend/requirements.txt` | Add `PySide6` |
| `docs/DEPENDENCIES.md` / `SETUP_AND_COMMANDS.md` | Document install + launch |

---

### Task 1: Phase 0 scaffold (tray + empty shell + tracker)

**Files:**
- Create: `backend/behavior/calt_desktop/__init__.py`
- Create: `backend/behavior/calt_desktop/__main__.py`
- Create: `backend/behavior/calt_desktop/app.py`
- Create: `backend/behavior/calt_desktop/main_window.py`
- Create: `backend/behavior/calt_desktop/tray.py`
- Create: `scripts/desktop_tracker/run_calt_desktop.bat`
- Create: `tests/test_calt_desktop_smoke.py`
- Modify: `backend/requirements.txt`
- Modify: `docs/DEPENDENCIES.md`, `docs/SETUP_AND_COMMANDS.md`

- [x] **Step 1:** Add `PySide6>=6.6.0` to `backend/requirements.txt` and note in DEPENDENCIES
- [x] **Step 2:** Implement `__main__.py` / `app.py`: single-instance (reuse `tracker_instance`), start `TrackerService`, run `QApplication`
- [x] **Step 3:** Implement `MainWindow` with placeholder tabs (Today, Bible, Plan, Rules, Schedules, Device, Watch, Voice, Settings)
- [x] **Step 4:** Implement `QSystemTrayIcon` — Open window, Open calendar (browser), Free time (stub → later PIN), Restart tracker, Quit
- [x] **Step 5:** Add `run_calt_desktop.bat` (env-only via `_common.bat`)
- [x] **Step 6:** Smoke test: `pytest tests/test_calt_desktop_smoke.py -q` (import + build window under `QT_QPA_PLATFORM=offscreen` if available)
- [x] **Step 7:** `pip install PySide6` in venv; verify `python -c "from PySide6.QtWidgets import QApplication"`
- [x] **Step 8:** Commit Phase 0

**Done when:** App launches, tray visible, tracker hub `:8765` up, old Tk tray not required for this entry point.

---

### Task 2: Phase 1 — Today + Rules + Schedules + Device + Bible/Plan stubs

**Files:**
- Create: `backend/behavior/calt_desktop/tabs/today.py`
- Create: `backend/behavior/calt_desktop/tabs/rules.py`
- Create: `backend/behavior/calt_desktop/tabs/schedules.py`
- Create: `backend/behavior/calt_desktop/tabs/device.py`
- Create: `backend/behavior/calt_desktop/tabs/bible.py`
- Create: `backend/behavior/calt_desktop/tabs/plan.py`
- Create: `backend/behavior/calt_desktop/dialogs.py`
- Modify: `main_window.py`, `tray.py`

- [x] **Step 1:** Today tab — live gate snapshot (mode, focus min, morning next) via `TrackerService.latest_gate()` / day_status helpers; refresh timer
- [x] **Step 2:** Rules tab — load/save productivity policy + category scores (reuse `productivity_policy` / `category_scores` modules) *(core fields: hard block, goal, exes; scores next)*
- [ ] **Step 3:** Schedules tab — load/save `gate_schedules.json`
- [ ] **Step 4:** Device tab — device_block status + apply/remove guidance (call `device_block` module)
- [ ] **Step 5:** Bible tab — open PDF/reader or link; mark bible done via existing morning APIs/modules
- [ ] **Step 6:** Plan tab — confirm plan CTA + “Edit calendar in browser” button to `http://localhost:5173/productivity`
- [ ] **Step 7:** Qt free-time PIN dialog + hard-block notice dialog; wire tray / TrackerService hooks to prefer Qt when calt_desktop is running
- [x] **Step 8:** Tests for policy load/save helpers (pure functions where possible)
- [ ] **Step 9:** Commit Phase 1

**Done when:** Can arm hard-block, edit schedules, see today status, confirm morning steps without opening Tk or web policy panels.

---

### Task 3: Phase 2 — Watch + Voice

**Files:**
- Create: `backend/behavior/calt_desktop/tabs/watch.py`
- Create: `backend/behavior/calt_desktop/tabs/voice.py`

- [ ] **Step 1:** Watch tab — hub health (`:8765/health`), LAN IP hint, token, sync instructions
- [ ] **Step 2:** Voice tab — `voice_notes.list_notes()`, play/open folder/download path
- [ ] **Step 3:** Settings tab — stack health, open Study, Jarvis pause hints
- [ ] **Step 4:** Tests for voice list helper; commit Phase 2

**Done when:** Watch setup and voice clips usable entirely from desktop app.

---

### Task 4: Phase 3 — Website slim-down

**Files:**
- Modify: `src/pages/ProductivityPage.tsx`
- Modify: related panels or wrap with “Managed in CALT Desktop” notice
- Modify: `docs/SETUP_AND_COMMANDS.md`, SESSION_LOG

- [ ] **Step 1:** Keep calendar + plan-vs-actual calendar flows on `/productivity`
- [ ] **Step 2:** Hide or stub policy / schedules / device / wearables / voice editors with CTA to launch desktop
- [ ] **Step 3:** Prefer desktop for morning gate when flag present (optional soft detection)
- [ ] **Step 4:** Point `run_desktop_tracker.bat` docs to prefer `run_calt_desktop.bat` (keep old as fallback)
- [ ] **Step 5:** Commit Phase 3

**Done when:** Website productivity page is calendar-centric; rules live in desktop.

---

### Task 5: Verification

- [ ] Focused pytest: calt_desktop smoke + gate/voice/device existing tests
- [ ] Manual: launch desktop, hub health, open Rules, free-time PIN
- [ ] Confirm restore tag still exists: `git tag -l restore/pre-calt-desktop-pyside6`

---

## Rollback

```bat
git checkout restore/pre-calt-desktop-pyside6
```

Or: `git reset --hard restore/pre-calt-desktop-pyside6` (destructive — only if owner asks).
