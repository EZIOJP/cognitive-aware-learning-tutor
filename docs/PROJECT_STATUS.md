# Project Status

Last updated: 2026-08-18

## Current focus

**Tracker API unified board** — `day-status` schema 3 embeds pulse, goals, focus quality, weekly snippet; Android + Life Tracker consume same payload. ActivityWatch export at `/api/behavior/export/activitywatch`. Competitive productivity lane complete.

Spec (quiz): [docs/superpowers/specs/2026-08-17-unified-quiz-completion-design.md](./superpowers/specs/2026-08-17-unified-quiz-completion-design.md)  
Plan (productivity): [docs/superpowers/plans/2026-08-18-competitive-features-priority.md](./superpowers/plans/2026-08-18-competitive-features-priority.md)  
Plan (tracker board): [docs/superpowers/plans/2026-08-18-tracker-api-unified-board.md](./superpowers/plans/2026-08-18-tracker-api-unified-board.md)

## Working now (daily-use product)

### Study loop
- Lecture Notes / Study Library — notes → quiz → Review Hub
- Review Hub + `StudyLoopWidget` with `next_step` / “Review N due”
- Math quiz multi-Q + Layer 0 skills + SymPy grading → ReviewCards
- GRE Vocab Phase 1 (read / cycle); **adaptive answers now also write vocab ReviewCards**
- Shared domains on Review Hub Start: study / math / vocab

### Removed (do not restore unless asked)
- Study Flow (`/study-flow`)
- Live corpus RAG Knowledge Base UI

### Productivity
- **CALT Desktop (PySide6)** — primary home for rules, bible/plan confirm, schedules, device block, watch hub, voice notes (`scripts\desktop_tracker\run_calt_desktop.bat`)
- Website `/productivity` — **calendar** + plan-vs-actual (rules/watch/voice moved to desktop)
- Desktop tracker engine (in-process with CALT Desktop) → plan vs actual, day ribbon, hub `:8765`
- Distraction gate (bible → confirm plan → study mode)
- **Productivity Pulse**, goals/alerts, activities inbox, shutdown ritual, weekly digest, focus quality
- **Unified day-status (schema 3)** — mobile/watch/web board; ActivityWatch export API

### Life / hub / extras
- Life Tracker (+ **TrackerDayBoard** today snapshot), Hub / AI Coach, wearables ingest, NutriNode, theme meteor

### Platform
- FastAPI `backend.main`, Alembic through `0028_wearable_ingest_replay`
- `run.bat` · Health `GET /health`

## Run locally

```bat
run.bat
```

Frontend: `http://localhost:5173` · API: `http://localhost:8000`  
Login: `admin` / `admin123`

## Explicitly later

- ESP32 / hardware, Math OCR Phase 3c, PostgreSQL, expanding Zepp beyond ingest
