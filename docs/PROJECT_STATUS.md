# Project Status

Last updated: 2026-09-06

## Current focus

**CALT Desktop · Focus (v2)** — Windows enforcer owns app kills; Web Dashboard is the control UI; Edge CALT Gate SoftLand; incubation + earned free-time ledger. EEG soft-fail ready. Quiz mandate done. See `AGENTS.md` (STOP after verify).

## Working now (daily-use product)

### Study loop
- Lecture Notes / Study Library — notes → quiz → Review Hub
- Review Hub + Study Loop; math + GRE → ReviewCards
- Shared domains on Review Hub: study / math / vocab

### Productivity / blocking
- **CALT Desktop · Focus** — Dashboard (web) + Rules/Schedules/Device editors; `run_calt_desktop.bat`
- **Windows enforcer** — hard-block kills without UI (`install_enforcer_service.ps1`)
- **CALT Gate + SelfTracker** — browser SoftLand (incubation-aware)
- Website `/productivity` — calendar + plan-vs-actual; banners point to Desktop
- Distraction gate (bible → plan → study) + day-status for Android/Life board
- Break/reward: incubation mandatory; earned ledger spend via PIN

### EEG
- Optional ESP32 BioAmp — soft-fail `/api/eeg/status`; flash docs in `docs/firmware/EEG_ESP32.md`

### Platform
- FastAPI `backend.main`, Alembic through `0033_break_reward`
- `run.bat` · Health `GET /health`

## Run locally

```bat
run.bat
scripts\desktop_tracker\run_calt_desktop.bat
scripts\desktop_tracker\install_enforcer_service.ps1 -Start
```

Frontend: `http://localhost:5173` · API: `http://localhost:8000`  
Login: `admin` / `admin123`

## Explicitly later

PyInstaller freeze, NSSM polish, Study Loop ledger earn, math OCR Phase 3c, PostgreSQL, expanding Zepp beyond ingest
