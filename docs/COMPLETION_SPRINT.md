# Agent Completion Sprint

**For the user:** Paste this at the start of any Cursor session when you want the agent to **finish the product**, not add random features:

```text
@AGENTS.md @docs/COMPLETION_SPRINT.md @docs/TASK_COMPLETION.md
Finish the product. Work Sprint by Sprint in order. Do not stop for permission between sprints unless blocked. Check off items in TASK_COMPLETION.md as you go. No new DB models except topic_study_runs if needed. No hub duplication.
```

**For the agent:** Your job is to make the app **daily-usable** per [TASK_COMPLETION.md](./TASK_COMPLETION.md) definition of done. Infrastructure exists — **connect it**.

---

## What “complete” means (and does not)

| In scope (“done”) | Out of scope (unless user asks) |
|-------------------|----------------------------------|
| One lecture loop works end-to-end | ESP32 / hardware firmware |
| GRE cycle still works | BKT, Neo4j, Kafka, microservices |
| Dashboard shows next study action | Community plugin, PostgreSQL prod |
| `npm run build` + core pytest green | Math Phase 3c OCR vision pipeline |
| Grounded notes default when corpus ready | WebGazer, full affective computing |

**Estimate:** ~5–8 focused agent sessions if executing sprints in order (not one shot).

---

## Sprint 1 — Backend orchestrator (blocking everything else)

**Goal:** One API chains existing services.

- [ ] Create `backend/transcripts/study_flow.py` with `start_topic_study_flow(...)`
- [ ] Chain: `hybrid_retrieve` → `generate_grounded_notes` (fallback: existing generate) → `ingest_lecture_handoff` → `generate_quiz_items` → save deck / start global quiz session
- [ ] Add `POST /api/transcripts/study-flow/start` in `router.py`
- [ ] Add `tests/test_study_flow.py` (mock LLM like `test_study_intel.py`)
- [ ] Document in [LLD.md](./LLD.md) §8 when merged

**Done when:** Postman/curl returns note path + quiz deck/session for one real transcript.

---

## Sprint 2 — Frontend stepper

**Goal:** User sees one flow, not five disconnected pages.

- [ ] Create `src/pages/study/TopicStudyFlowPage.tsx` — steps: Topic → Notes → Quiz → Review
- [ ] Register route `/study-flow` in `src/plugins/core_plugins.tsx`
- [ ] Add `startStudyFlow()` to `src/api/transcriptsClient.ts`
- [ ] Add **Study this topic** on `LectureNotesPage.tsx` → navigates to stepper with topic + transcript
- [ ] After quiz complete, redirect to `/review` or show due count

**Done when:** User clicks one button and reaches quiz without choosing code paths.

---

## Sprint 3 — Unify paths (remove confusion)

**Goal:** One obvious default; legacy labeled.

- [ ] When `CORPUS_GROUNDED_NOTES=1` + corpus available: Studio + web generate prefer grounded (or show “RAG mode” badge)
- [ ] Label legacy summarization “No corpus / legacy” in UI
- [ ] Lecture quiz always uses `/api/quiz` global path (not vocab adaptive)
- [ ] `StudyLoopWidget` uses only `/api/quiz/backlog` for recommended action

**Done when:** [TASK_COMPLETION.md](./TASK_COMPLETION.md) Lane B1–B3 checked.

---

## Sprint 4 — Verify & fix regressions

**Goal:** Nothing broken that was working.

- [ ] Run Lane A5 manual acceptance (one lecture) — document transcript used in SESSION_LOG
- [ ] Run Lane C GRE regression checklist
- [ ] `python -m pytest tests/ -q`
- [ ] `python -m pytest tests/test_corpus.py -m integration` if corpus deps installed
- [ ] `npm run build`

**Done when:** Definition of done rows 1–8 in TASK_COMPLETION all pass.

---

## Sprint 5 — Polish (only after Sprint 4)

**Goal:** Feels finished, not prototype.

- [ ] Empty states on Lecture Notes, Review Hub, Knowledge Base
- [ ] Loading states on study-flow + corpus job polling
- [ ] `.env.example` or SETUP doc lists `CORPUS_GROUNDED_NOTES=1`
- [ ] Update PROJECT_STATUS.md date + “complete for daily use”
- [ ] Prune stale items in TASKS.md

**Optional:** `topic_study_runs` table + Alembic if resume/history needed.

---

## Agent rules during completion sprint

1. **Connect, don’t duplicate** — call existing functions; no EnrichedNote / UserMastery / hub study routes.
2. **Sensible size changes OK** — orchestrator + stepper + path unification are **encouraged**, not “scope creep.”
3. **One sprint per session minimum** — finish Sprint N before starting N+1.
4. **If blocked** (missing transcript, corpus empty, LLM off) — implement graceful fallback + UI message; log in SESSION_LOG.
5. **Commits** — only when user asks.

---

## File map (quick reference)

| Sprint | Backend | Frontend |
|--------|---------|----------|
| 1 | `backend/transcripts/study_flow.py`, `router.py` | — |
| 2 | — | `TopicStudyFlowPage.tsx`, `transcriptsClient.ts`, `core_plugins.tsx` |
| 3 | `grounded_notes.py`, `transcripts/router.py` | `LectureNotesPage.tsx`, `StudyLoopWidget.tsx` |
| 4 | tests | — |
| 5 | — | empty states, docs |

---

## Related docs

- [TASK_COMPLETION.md](./TASK_COMPLETION.md) — full checklist (check off as sprints complete)
- [HLD.md](./HLD.md) · [LLD.md](./LLD.md) — architecture
- [AGENTS.md](../AGENTS.md) — agent role
