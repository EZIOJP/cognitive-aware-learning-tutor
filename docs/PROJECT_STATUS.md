# Project Status

Last updated: 2026-08-18

## Current focus

**Competitive productivity lane complete** — Pulse, goals/alerts, activities inbox, shutdown ritual, away prompt, weekly digest, focus quality, gate schedules. Unified quiz mandate remains verified (`757` pytest green).

Spec (quiz): [docs/superpowers/specs/2026-08-17-unified-quiz-completion-design.md](./superpowers/specs/2026-08-17-unified-quiz-completion-design.md)  
Plan (productivity): [docs/superpowers/plans/2026-08-18-competitive-features-priority.md](./superpowers/plans/2026-08-18-competitive-features-priority.md)

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
- Desktop tracker → plan vs actual, day ribbon (sleep-clipped overlay), calendar (day view default; no Today panel)
- Policy + propose plan + routines + week export (**wearables included**)
- Distraction gate (bible → confirm plan → study mode)
- **Productivity Pulse**, goals/alerts, activities inbox, shutdown ritual, weekly digest, focus quality, recurring gate schedules

### Life / hub / extras
- Life Tracker, Hub / AI Coach, wearables ingest, NutriNode, theme meteor

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
