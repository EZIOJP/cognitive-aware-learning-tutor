# Agent Context

You are finishing a **local-first study platform** for daily personal use.

**Mandate (2026-08-17 — unattended completion):** While the owner is away, execute the approved design [docs/superpowers/specs/2026-08-17-unified-quiz-completion-design.md](docs/superpowers/specs/2026-08-17-unified-quiz-completion-design.md). Prefer proof + smallest wiring. Owner will review and tweak on return.

---

## What “complete” means (this mandate)

```text
ONE quiz engine (/api/quiz) with modes: study (lecture notes) · math · vocab
ALL graded lasting knowledge → ReviewCard FSRS → /review + dashboard "Review N due"
Notes + quiz generation follow Cursor rules (grounded, linted, prefer_notes)
Productivity Calendar tracking visuals finished (empty states, adherence, plan-vs-actual)
PLUS: npm run build passes, core pytest green, GRE cycle still works
```

**Not required:** restoring Study Flow / corpus RAG KB, hardware, BKT, Neo4j, math OCR Phase 3c, PostgreSQL, wearables/hard-block expansion.

**Already shipped (keep working):** distraction gate, wearables ingest, planner/calendar, morning bible+plan confirm, productivity export (incl. watch metrics), math Layer 0 + SymPy path.

---

## Current focus

| Phase | Deliverable | Status |
|-------|-------------|--------|
| 0 | Spec + AGENTS + notes/quiz Cursor rules | **Done** |
| 1 | Vocab adaptive → ReviewCard + unified CTAs | **Done** |
| 2 | Notes/quiz generation guardrails + tests | **Done** |
| 3 | Mixed daily practice / StudyLoop | **Done** (due → Review Hub; Cycle stays adaptive + SRS bridge) |
| 4 | Productivity infographic polish | **Done** (sleep-clip ribbon, watch sleep score, heatmap labels) |
| 5 | Verify (pytest + build + A5 notes) | **pytest + build green** — A5 lecture walkthrough on owner return |

See [docs/SESSION_LOG.md](docs/SESSION_LOG.md) and [docs/PROJECT_STATUS.md](docs/PROJECT_STATUS.md).

---

## How to work

1. **Anchor:** `@AGENTS.md` `@docs/superpowers/specs/2026-08-17-unified-quiz-completion-design.md` `@docs/decisions/ADR-001-quiz-practice-orchestration.md`
2. **Superpowers:** `verification-before-completion`, `systematic-debugging`, `executing-plans` / `subagent-driven-development`
3. **Wire, don’t migrate** — no second SRS, no second quiz runner, no `/api/home/summary`
4. **Correct layers:**
   - Study notes/quiz gen: `backend/transcripts/`
   - Quiz/SRS/backlog: `backend/quiz/`
   - Math drills: `backend/math/` → enqueue via quiz ReviewCards
   - GRE bank still in `backend/vocab/` but **sessions should prefer `/api/quiz` domain=vocab**; adaptive routes may remain as shims that also write ReviewCards
5. **Do not extend:** `UniversalReadMode.jsx`, `vocab_backend.py` shim, `backend_example.py`
6. **Do not resurrect** live corpus RAG / Study Flow unless the owner reopens that lane
7. **Backend:** `backend.main` · Alembic — [docs/MIGRATIONS.md](docs/MIGRATIONS.md)
8. **Commits / push:** only when the user asks (or when continuing an explicit push request)
9. **Check off** [docs/TASK_COMPLETION.md](docs/TASK_COMPLETION.md) only when verified

---

## Stack (short)

```text
React (Vite) → FastAPI → SQLite
APIs: /api/transcripts · /api/quiz · /api/vocab · /api/math · /api/hub · /api/planner · /api/behavior
Daily study path: Lecture Notes → quiz → Review Hub
```

---

## Dev servers

```bat
run.bat
```

Frontend: `http://localhost:5173` · API: `http://localhost:8000` · Health: `GET /health`

---

## Touch only when user asks

New wearables product features, hard-block UX redesign, life-clock skins expansion, hardware, platform rewrite, restoring Knowledge Base / Study Flow.

---

## Docs

| Doc | Use |
|-----|-----|
| [docs/superpowers/specs/2026-08-17-unified-quiz-completion-design.md](docs/superpowers/specs/2026-08-17-unified-quiz-completion-design.md) | **Active mandate** |
| [docs/decisions/ADR-001-quiz-practice-orchestration.md](docs/decisions/ADR-001-quiz-practice-orchestration.md) | Quiz architecture lock |
| [docs/TASK_COMPLETION.md](docs/TASK_COMPLETION.md) | Master checklist |
| [docs/PROJECT_STATUS.md](docs/PROJECT_STATUS.md) | What’s working today |
| [docs/SESSION_LOG.md](docs/SESSION_LOG.md) | Per-session progress |
| `.cursor/rules/notes-generation.mdc` | Notes gen policy |
| `.cursor/rules/quiz-generation.mdc` | Quiz gen / SRS policy |
| `.cursor/skills/study-completion-workflow/SKILL.md` | Repo workflow |
