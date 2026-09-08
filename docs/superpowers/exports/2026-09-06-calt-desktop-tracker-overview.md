# CALT Desktop Tracker — Owner Overview

**Date:** 2026-09-06  
**Audience:** You (daily use + install)  
**Related:** [README index](./2026-09-06-calt-desktop-tracker-README.md)

---

## What “new CALT Desktop Tracker” means

Not a second Cold Turkey. Three pieces that share **one SQLite** (`data/vocab_app.db`):

| Piece | Job | You see it as |
|-------|-----|----------------|
| **Web Focus** | Control panel (arm, free time, earned, enforcer status) | Browser → `/productivity/focus` |
| **SelfTracker extension** | Which **tab** is open/active in Edge | Productivity app list → **Microsoft Edge** + sites |
| **Native enforcer** (`calt_enforcer.exe`) | Kill blocked apps; track non-browser windows | Task Scheduler / Windows Service |

Legacy PySide6 Qt Desktop is optional only: `run_calt_desktop_qt.bat`.

---

## Daily loop

1. Start stack: `run.bat` (API `:8000` + Vite).
2. Enforcer keep-alive (once):  
   `powershell -ExecutionPolicy Bypass -File scripts\desktop_tracker\install_enforcer_service.ps1 -Start`
3. Open Focus: `scripts\desktop_tracker\run_calt_desktop.bat`  
   or go to `http://127.0.0.1:5173/productivity/focus`
4. Edge extensions loaded: **SelfTracker** + **CALT Gate** (reload after updates).
5. Check usage: `/productivity` → Desktop App Usage.

---

## Where time is counted

| Activity | Counted as | Source |
|----------|------------|--------|
| Edge tab (youtube.com, etc.) | **Microsoft Edge** + site row | extension `SESSION_END` |
| Cursor / VS Code / games | App exe name | native (or Python fallback) |
| CALT study SPA on localhost | Study presence (not Edge tab spam) | `calt_spa` |

Bare Edge process time from desktop/native is **ignored** so it does not double-count with SelfTracker.

---

## Installer (optional)

```bat
scripts\desktop_tracker\build_native_enforcer.bat
scripts\desktop_tracker\compile_installer.bat
```

Needs **Inno Setup 6**. Output: `scripts\desktop_tracker\Output\CALTDesktopSetup-0.2.1-v2d-native.exe`  
Still needs your git clone + `.venv` — installer is shortcuts + enforcer helpers, not a frozen app.

Docs: `scripts/desktop_tracker/INSTALLER.md`

---

## Morning smoke

Full checklist: [2026-09-07-morning-smoke.md](./2026-09-07-morning-smoke.md)

```bat
scripts\desktop_tracker\run_native_enforcer_console.bat
REM Focus → Arm notepad.exe → Notepad dies
REM Edge tab → /productivity shows Microsoft Edge + site
```

## Owner checklist (still on you)

- [ ] Reload SelfTracker + Gate in `edge://extensions`
- [ ] Admin service (stronger than Task Scheduler):  
      `powershell -File scripts\desktop_tracker\install_native_enforcer.ps1`
- [ ] Install Inno Setup 6 if you want a Setup EXE
- [ ] Confirm SoftLand still hits `:8000` while locked

---

## Do not

- Do not open / decompile Cold Turkey from `Desktop\ZXCazsd\`
- Do not expect Qt panels to be the main control UI anymore
- Do not run two kill owners fighting (native lock vs Python) — native wins when lock is fresh
- Do not reintroduce Python into the kill/track loop
