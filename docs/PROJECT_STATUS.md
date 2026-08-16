# Project Status

Last updated: 2026-08-05

## Current focus

Tight gate UX (2026-08-05): SelfTracker **1.5.3** on **Edge only** — browser catalog soft-locks other browsers + installers; Settings lists Edge SelfTracker load/reload. Restart tracker + reload extension after pull.


Study Flow and corpus/Knowledge Base were **removed** (2026-08-04) per user request. Daily study path: **Lecture Notes** (transcript → notes) → quiz → **Review Hub**. GRE vocab remains.

## Working now (daily-use product)

### Study loop
- Lecture Notes / Study Library — notes, quiz, mermaid (non-corpus / non-RAG path)
- Review Hub + `StudyLoopWidget` with `next_step` / “Review N due”
- Math quiz multi-Q + Layer 0 skills + SymPy grading path
- GRE Vocab Phase 1 (read / cycle / low-mastery)

### Removed
- Study Flow (`/study-flow`, `POST /api/transcripts/study-flow/start`)
- Knowledge Base UI (`/knowledge-base`) and live corpus RAG API (`/api/corpus`); thin stubs remain so imports do not break boot

### Productivity
- Desktop tracker → plan vs actual, day ribbon, calendar
- Productivity **policy** (productive vs distraction) + session overrides
- LLM **propose plan** → preview → multi-day apply
- Routines, week export, Google Calendar sync panel
- Distraction hard-block (policy + gate) when enabled

### Life / hub / extras
- Life Tracker + Life Clock skins
- Hub / AI Coach chat
- Wearables / Zepp daily ingest bridge (migrations `0027`)
- Journal, NutriNode widget, theme meteor / easter eggs

### Platform
- FastAPI `backend.main`, Alembic through `0027_wearable_daily`
- Plugins registry, Feature Studio, JWT auth
- `run.bat` / `newrun.bat` / `control.bat` + `scripts/server_lifecycle.py`

## Run locally

```bat
run.bat
```

Health: `GET http://127.0.0.1:8000/health` → `schema_ok: true`  
Frontend: `http://localhost:5173`

Prototype login: `admin` / `admin123`

## Cape-time checklist

| Check | Doc |
|-------|-----|
| One lecture A5 walkthrough | [TASK_COMPLETION.md](./TASK_COMPLETION.md) Lane A5 |
| GRE regression | Lane C |
| pytest + build | Lane G1 |
| Docs / empty states | Sprint 5 |

## Explicitly later (not cape blockers)

- ESP32 / hardware firmware
- Math OCR Phase 3c / WebGazer
- PostgreSQL + community plugins
- Expanding Zepp OS app beyond current ingest bridge
