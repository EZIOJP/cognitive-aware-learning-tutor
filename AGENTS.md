# Agent Context

You are finishing a **local-first study platform** for daily personal use.

**Mandate (2026-07-19 — cape time):** Most build work is done. Run [docs/COMPLETION_SPRINT.md](docs/COMPLETION_SPRINT.md) **Sprint 4 verification**, then **Sprint 5 polish**. Do **not** open new feature lanes. Fix only what acceptance proves broken.

---

## What “complete” means

```text
One button: Study topic → grounded notes → quiz → SRS → dashboard "Review N due"
PLUS: GRE cycle still works, npm run build passes, core tests green
```

**Not required for complete:** hardware, BKT, Neo4j, microservices, math OCR Phase 3c, PostgreSQL.

**Already shipped beyond the original loop (keep working, don’t expand in cape time):** productivity policy + LLM propose-plan, distraction gate, wearables/Zepp ingest, math skills Layer 0, Google Calendar sync, per-page easter eggs.

---

## Current focus

See [docs/SESSION_LOG.md](docs/SESSION_LOG.md). Default: **Sprint 4 (verify)** → **Sprint 5 (polish)**.

| Sprint | Deliverable | Status |
|--------|-------------|--------|
| 1 | `POST /api/transcripts/study-flow/start` | ✅ |
| 2 | `TopicStudyFlowPage.tsx` | ✅ |
| 3 | Unified note/quiz paths + `next_step` | ✅ |
| 4 | GRE + pytest + build + one-lecture acceptance | **Do now** |
| 5 | Empty states, docs, PROJECT_STATUS | After 4 |

---

## How to work

1. **Anchor:** `@AGENTS.md` `@docs/COMPLETION_SPRINT.md` `@docs/TASK_COMPLETION.md`
2. **Superpowers:** Prefer `verification-before-completion` and `systematic-debugging`. Plans under `docs/superpowers/plans/` are **archives** unless the user reopens one.
3. **Wire, don’t migrate** — no duplicate models.
4. **Correct layer:** `backend/transcripts/`, `backend/corpus/`, `backend/quiz/` for study loop.
5. **Do not extend:** `UniversalReadMode.jsx`, `vocab_backend.py` shim, `backend_example.py`.
6. **Backend:** `backend.main` · Alembic — [docs/MIGRATIONS.md](docs/MIGRATIONS.md).
7. **Check off** TASK_COMPLETION when verified (not when code merely exists).

---

## Stack (short)

```text
React (Vite) → FastAPI → SQLite + corpus (Qdrant/BM25)
APIs: /api/transcripts · /api/corpus · /api/quiz · /api/vocab · /api/hub · /api/planner · /api/behavior
```

`CORPUS_GROUNDED_NOTES=1` + built corpus for RAG notes.

---

## Dev servers

```bat
run.bat
```

Frontend: `http://localhost:5173` · API: `http://localhost:8000` · Health: `GET /health`

---

## Touch only when user asks

New wearables features, hard-block UX redesign, life-clock skins expansion, hardware, platform rewrite.

GRE Phase 1 is **complete** — regression-test in Sprint 4 only.

---

## Docs

| Doc | Use |
|-----|-----|
| [docs/COMPLETION_SPRINT.md](docs/COMPLETION_SPRINT.md) | **Cape-time board** — verify then polish |
| [docs/TASK_COMPLETION.md](docs/TASK_COMPLETION.md) | Master checklist + definition of done |
| [docs/HLD.md](docs/HLD.md) · [docs/LLD.md](docs/LLD.md) | Architecture |
| [docs/SESSION_LOG.md](docs/SESSION_LOG.md) | Per-session progress |
| [docs/PROJECT_STATUS.md](docs/PROJECT_STATUS.md) | What’s working today |
| `.cursor/skills/study-completion-workflow/SKILL.md` | Agent workflow for this repo |
