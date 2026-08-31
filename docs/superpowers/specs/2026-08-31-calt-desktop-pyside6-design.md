# CALT Desktop (PySide6) — Productivity home

**Date:** 2026-08-31  
**Status:** Draft — awaiting owner approval  
**Scope:** Move productivity / gate / bible-morning / watch / voice into one Python desktop app. Study stack stays in the browser. **Productivity calendar** stays on the website for now.

---

## 1. Goal

Own **day rules and productivity control** in a single Windows desktop app built with **PySide6** (one process: UI + tracker + hub). Stop scattering rules across Tk popups and the Vite Productivity page.

**Non-goals (this lane):** OCR, quiz/GRE/math notes rewrite, Electron, phone Device Gate, restoring Study Flow / RAG.

---

## 2. Split: Desktop vs Website

### CALT Desktop (PySide6) — owns

| Area | Today (web / Tk) | Desktop |
|------|------------------|---------|
| Morning bible | `/bible` | In-app bible reader (reuse PDF/embed path from tracker) |
| Morning plan confirm | Confirm plan button / morning gate | Confirm plan UI |
| Rules / hard block / goals / scores | `ProductivityPolicyPanel` + Tk rules | Rules tab |
| Gate schedules | `GateSchedulesPanel` | Schedules tab |
| Device / porn hosts block | `DeviceBlockPanel` | Device block tab |
| Session overrides / classification | panels on Productivity page | Settings / review tab |
| Planning settings (not calendar grid) | `PlanningSettingsPanel` | Settings |
| Watch ↔ PC hub + CALT Sync status | `WearablesSyncPanel`, hub banner | Watch sync tab |
| Voice notes (list / download / play) | `VoiceNotesPanel` | Voice tab |
| Hard-block notice / free-time PIN / Jarvis toast | Tk popups | Native Qt dialogs / tray / notifications |
| Tracker tray | `pystray` + Tk | `QSystemTrayIcon` |

### Website (Vite) — keeps

| Area | Why |
|------|-----|
| **Productivity calendar** (`PlannerCalendar`, plan-vs-actual grid, propose week, routines materialize on calendar) | Complex React calendar stays where it is for now |
| Study: GRE, math, lecture notes, quiz, Review Hub | Unrelated to gate ownership |
| Optional thin links | “Open CALT Desktop” / deep-link for rules if user hits old productivity routes |

### Explicitly **removed from website** over time (redirect or stub)

- Productivity policy / gate schedules / device block editors  
- Wearables sync + voice notes panels  
- Morning bible + plan confirm as the **primary** gate path (desktop becomes primary; SPA soft-gate can call same APIs or detect “confirmed today”)

Calendar data **APIs** stay shared (same FastAPI / SQLite). Desktop may later *read* planner blocks for “today’s plan” glance; editing the full calendar grid remains web-only in v1.

---

## 3. Architecture

```text
pythonw -m backend.behavior.calt_desktop
│
├── QApplication (main UI thread)
│   ├── MainWindow — tabs below
│   ├── QSystemTrayIcon — Free time PIN, Open, Restart, Quit(PIN)
│   └── Dialogs — hard-block, stack-down, away prompt
│
├── Background (QThread / existing tracker threads)
│   ├── TrackerService — app poll, session SQLite, hard-block kills
│   ├── tracker_hub :8765 — watch sync, voice-note upload, gate mirror
│   └── Voice agent (optional) — Jarvis speak, no Tk toast
│
└── Same backend APIs / DB
    ├── FastAPI :8000 when study stack needed (or desktop calls DB/modules in-process)
    └── SQLite vocab_app.db + data/behavior/*.json
```

**One process.** No Electron sidecar. Extensions still poll gate JSON (prefer hub `:8765` or `:8000` — same payload as today).

**UI stack:** PySide6 + Qt Style Sheets. Optional later: `QWebEngineView` only if embedding calendar is required; **v1 does not embed the calendar.**

---

## 4. Main window tabs (v1)

1. **Today** — mode (study/free/locked), focus minutes vs goal, morning next step, glance board, open Study in browser button  
2. **Bible** — morning reading + mark done (feeds morning gate)  
3. **Plan** — confirm today’s plan (links to web calendar for full edit: “Edit calendar in browser”)  
4. **Rules** — hard block, goals, category scores, kill exes, free-time override  
5. **Schedules** — Freedom-style recurring windows  
6. **Device** — hosts / porn / social block apply status  
7. **Watch** — hub health, CALT Sync setup (IP, token), last sync watermark  
8. **Voice** — list / play / download / delete voice notes from `data/voice_notes/`  
9. **Settings** — planning prefs, demo clock, stack health, Jarvis on/off  

---

## 5. Rule model (unchanged engine, clearer UI)

Desktop **edits** the same stores the web already uses:

- SQLite `productivity_policy`, `category_scores`  
- `data/behavior/gate_schedules.json`  
- `data/behavior/device_block.json` / porn list  
- `data/behavior/browser_free_override.json`  

Live gate still computed by `distraction_gate` / `browser_gate_policy`. Desktop shows a **live preview**: “YouTube → blocked (study mode)”.

---

## 6. Deprecations

| Remove / freeze | Replacement |
|-----------------|-------------|
| `tracker_rules_gui.py` | Today + Rules tabs |
| `tracker_block_gui.py` | Qt hard-block dialog |
| `tracker_bible_embed.py` (Tk) | Bible tab |
| `tracker_schedule_gui.py`, `tracker_reward_gui.py` | Plan / Rules |
| `jarvis_toast.py` (Tk) | Qt tray notification or small frameless toast |
| `voice_agent/chat_ui.py` (Tk) | Optional later Voice chat panel; not blocking v1 |
| Productivity page panels listed in §2 | Stub: “Managed in CALT Desktop” + calendar only |

Keep `tracker_service.py`, `tracker_hub.py`, gate modules as the engine.

---

## 7. Phased delivery

### Phase 0 — Scaffold (ship early)

- Package entry: `backend/behavior/calt_desktop/` (app, main_window, tray)  
- Dependency: `PySide6` in project deps docs  
- Launch: tray + empty main window + existing `TrackerService` started in-process  
- Parallel-run with old tray until stable; then switch `run_desktop_tracker.bat` → calt_desktop  

### Phase 1 — Morning + Rules

- Bible tab + plan confirm  
- Rules + Schedules + Device (parity with web panels)  
- Replace Tk free-time PIN + hard-block popup  

### Phase 2 — Watch + Voice

- Watch hub status + sync instructions  
- Voice notes list/play/download (same files as web API)  

### Phase 3 — Website slim-down

- `/productivity` focuses on **calendar** (+ plan-vs-actual on calendar)  
- Other productivity tabs → redirect copy or deep-link `calt-desktop://` / bat launch  
- SPA morning gate: prefer “already confirmed via desktop” from API  

### Phase 4 (optional, later)

- Read-only “today’s blocks” in desktop Plan tab (API)  
- Embed calendar via QWebEngineView **only if** owner wants calendar off the website  

---

## 8. Success criteria

- Single tray icon runs tracker + hub + productivity UI  
- No Tk for gate/rules/bible/block in normal path  
- Extensions and watch still work via `:8765`  
- Website productivity calendar still works for planning  
- Study app unchanged for quiz/GRE/math/notes  
- OCR lane untouched  

---

## 9. Risks

| Risk | Mitigation |
|------|------------|
| Qt UI thread vs tracker poll | Tracker stays off UI thread; signals/slots for UI updates |
| PySide6 install size | Accept for desktop product; document `pip install PySide6` |
| Morning flow split (desktop vs SPA) | Shared API flags (`morning.confirmed`); either client can complete |
| Calendar-only on web feels incomplete | Plan tab “Open calendar” button; Phase 4 optional embed |

---

## 10. Decision log

| Decision | Choice |
|----------|--------|
| UI toolkit | **PySide6** (not CTk, not Electron) |
| Process model | **One Python process** (UI + tracker + hub) |
| Website residual | **Productivity calendar** (+ study stack) |
| Watch + Voice | **In desktop app** |
| Bible + plan settings | **In desktop app** |
| Calendar full editor | **Stays on website (v1)** |
