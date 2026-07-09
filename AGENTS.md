# Agent Context

You are finishing a **local-first study platform** for daily personal use — not prototyping forever.

**Your mandate:** Execute [docs/COMPLETION_SPRINT.md](docs/COMPLETION_SPRINT.md) sprints in order until [docs/TASK_COMPLETION.md](docs/TASK_COMPLETION.md) definition of done passes. **Connect existing pieces.** Do not add parallel systems.

The user is tired of partial work. **Finish sprints, don’t ask for permission between steps** unless truly blocked (missing data, env, ambiguous product choice).

---

## What “complete” means

```text
One button: Study topic → grounded notes → quiz → SRS → dashboard "Review N due"
PLUS: GRE cycle still works, npm run build passes, core tests green
```

**Not required for complete:** hardware, BKT, Neo4j, microservices, math OCR Phase 3c, PostgreSQL.

---

## Current sprint focus

See [docs/SESSION_LOG.md](docs/SESSION_LOG.md). Default: **Sprint 1** (or next unchecked sprint in COMPLETION_SPRINT).

| Sprint | Deliverable |
|--------|-------------|
| 1 | `POST /api/transcripts/study-flow/start` orchestrator |
| 2 | `TopicStudyFlowPage.tsx` stepper UI |
| 3 | Unify note/quiz paths (grounded default, global quiz for lectures) |
| 4 | Verify GRE + pytest + build + one-lecture acceptance |
| 5 | Polish empty states, docs, PROJECT_STATUS |

---

## How to work

1. **Anchor:** `@AGENTS.md` `@docs/COMPLETION_SPRINT.md` `@docs/TASK_COMPLETION.md` `@docs/HLD.md` `@docs/LLD.md`
2. **Superpowers:** Read `.cursor/skills/study-completion-workflow/SKILL.md` for sprint order. Use `.cursor/skills/superpowers/` skills (brainstorming, writing-plans, executing-plans, systematic-debugging). Cursor tool map: `.cursor/skills/superpowers/using-superpowers/references/cursor-tools.md`
3. **Wire, don’t migrate:** Use `hybrid_retrieve`, `generate_grounded_notes`, `ingest_lecture_handoff`, `generate_quiz_items`, `quiz/handler`. No duplicate models unless user explicitly asks.
3. **Sensible connection changes are encouraged** — orchestrator, stepper, unified defaults are **not** scope creep.
4. **Correct layer:** `backend/transcripts/`, `backend/corpus/`, `backend/quiz/` — not hub for study flow logic.
5. **Naming:** `TopicStudyFlowPage`, `topic_study_runs` — not `StudySession` (clashes with EEG context / hub sessions).
6. **Do not extend:** `UniversalReadMode.jsx`, `vocab_backend.py` shim, `backend_example.py`.
7. **Backend:** `backend/main.py` · Alembic for schema — [docs/MIGRATIONS.md](docs/MIGRATIONS.md).
8. **Check off** TASK_COMPLETION items as you complete them.

---

## Stack (short)

```text
React (Vite) → FastAPI → SQLite + corpus (Qdrant/BM25)
APIs: /api/transcripts · /api/corpus · /api/quiz · /api/vocab · /api/hub
```

`CORPUS_GROUNDED_NOTES=1` + built corpus (~3500 chunks) for RAG notes.

---

## Dev servers

```bat
run.bat
```

Frontend: `http://localhost:5173` · API: `http://localhost:8000` · Health: `GET /health`

---

## Touch only when user asks

Pomodoro, EEG, Life Tracker, NutriNode, math vision pipeline, hardware, platform rewrite.

GRE Phase 1 is **complete** — regression-test in Sprint 4, don’t refactor unless broken.

---

## Docs

| Doc | Use |
|-----|-----|
| [docs/COMPLETION_SPRINT.md](docs/COMPLETION_SPRINT.md) | **Start here** — ordered sprints |
| [docs/TASK_COMPLETION.md](docs/TASK_COMPLETION.md) | Master checklist + definition of done |
| [docs/HLD.md](docs/HLD.md) · [docs/LLD.md](docs/LLD.md) | Architecture |
| [docs/SESSION_LOG.md](docs/SESSION_LOG.md) | Per-session progress |
| [docs/README.md](docs/README.md) | Full index |
| `.cursor/skills/study-completion-workflow/SKILL.md` | Agent workflow for this repo |
| `.cursor/skills/superpowers/` | Superpowers skills (TDD, plans, debugging) |
