# Agent Completion Sprint → Active Mandate

**Status (2026-08-17):** Cape-time Study Flow checklist is **archived**. Active work is **unified quiz completion** — see [superpowers/specs/2026-08-17-unified-quiz-completion-design.md](./superpowers/specs/2026-08-17-unified-quiz-completion-design.md) and [AGENTS.md](../AGENTS.md).

**For the user / agent:**

```text
@AGENTS.md @docs/superpowers/specs/2026-08-17-unified-quiz-completion-design.md
Unify study + math + vocab into /api/quiz → Review Hub. Enforce notes/quiz rules. Polish productivity tracking visuals. No Study Flow / RAG resurrection.
```

---

## What “complete” means (current)

| In scope | Out of scope |
|----------|--------------|
| One quiz engine, three modes → shared FSRS | Restoring Study Flow / corpus KB |
| Notes + quiz generation rules | Hardware / OCR 3c / PostgreSQL |
| Productivity Calendar tracking polish | Wearables / hard-block expansion |
| `npm run build` + core pytest green | Second SRS or home summary brain |

---

## Sprint board (historical 1–3 kept for archive)

| Sprint | Goal | Status |
|--------|------|--------|
| 1–3 | Study-flow / notes / quiz wiring | **Removed 2026-08-04** — live loop is Lecture Notes → `/api/quiz` → Review Hub |
| Unified quiz | Vocab+math+study → ReviewCards | **Active** |
| Productivity polish | Infographics / empty states | **Active** |
| Verify | pytest + build + walkthrough notes | After above |

Historical Sprint 1–2 checkboxes below refer to **deleted** files (`study_flow.py`, `/study-flow`). Do not restore them. Canonical loop: Lecture Notes → GlobalQuizRunner → Review Hub.

Historical Sprint 4/5 verify items still useful as a regression checklist in [TASK_COMPLETION.md](./TASK_COMPLETION.md).

---

## Agent rules

1. Prefer ADR-001 + 2026-08-17 unified quiz spec over this file’s older “cape only” language.
2. Wire, don’t migrate — no duplicate quiz/SRS systems.
3. Commits only when user asks.
4. Check off TASK_COMPLETION only when verified.

---

## What “complete” means (and does not)

| In scope (“done”) | Out of scope (unless user asks) |
|-------------------|----------------------------------|
| One lecture loop works end-to-end | ESP32 / hardware firmware |
| GRE cycle still works | BKT, Neo4j, Kafka, microservices |
| Dashboard shows next study action | Community plugin, PostgreSQL prod |
| `npm run build` + core pytest green | Math Phase 3c OCR vision pipeline |
| Grounded notes default when corpus ready | WebGazer, full affective computing |

Extra product that **already shipped beyond the original sprint** (productivity policy, LLM propose-plan, wearables bridge, math skills Layer 0, easter eggs) is **bonus** — keep it working; do not expand it in cape time.

---

## Sprint board

| Sprint | Goal | Status |
|--------|------|--------|
| 1 | Backend study-flow orchestrator | **Done** |
| 2 | `TopicStudyFlowPage` stepper | **Done** |
| 3 | Unify notes/quiz defaults | **Done** (grounded default + global quiz + `next_step`) |
| 4 | Verify & fix regressions | **Cape time — do this** |
| 5 | Polish + docs status | **Cape time — after 4** |

---

## Sprint 1 — Backend orchestrator ✅

- [x] `backend/transcripts/study_flow.py` + `POST /api/transcripts/study-flow/start`
- [x] Chain retrieve → notes → handoff → quiz
- [x] `tests/test_study_flow.py`
- [x] Documented in LLD / ADR-001

---

## Sprint 2 — Frontend stepper ✅

- [x] `TopicStudyFlowPage.tsx` — Topic → Notes → Quiz → Review
- [x] Route `/study-flow` in `core_plugins.tsx`
- [x] `startStudyFlow()` in `transcriptsClient.ts`
- [x] Study Loop / hub links into the flow

---

## Sprint 3 — Unify paths ✅

- [x] Grounded / hybrid notes path when corpus configured
- [x] Lecture quiz uses `/api/quiz` global path
- [x] `StudyLoopWidget` + `next_step` from backlog/complete
- [x] Math multi-Q + skills Layer 0 (quiz practice loop)

---

## Sprint 4 — Verify & fix regressions (current)

**Goal:** Prove daily-use, don’t invent.

- [ ] Run Lane A5 manual acceptance (one lecture) — note transcript in [SESSION_LOG.md](./SESSION_LOG.md)
- [ ] Run Lane C GRE regression checklist
- [ ] `python -m pytest tests/ -q`
- [ ] `python -m pytest tests/test_corpus.py -m integration` if corpus deps installed
- [ ] `npm run build`
- [ ] `GET /health` → `schema_ok: true` (migrations through `0027_wearable_daily` as needed)

**Done when:** Definition of done rows 1–8 in [TASK_COMPLETION.md](./TASK_COMPLETION.md) pass.

---

## Sprint 5 — Polish (only after Sprint 4)

**Goal:** Feels finished, not prototype.

- [ ] Empty states on Lecture Notes, Review Hub, Knowledge Base (fill gaps only)
- [ ] Loading states on study-flow + corpus job polling
- [ ] Confirm `.env.example` lists `CORPUS_GROUNDED_NOTES=1`
- [ ] Update [PROJECT_STATUS.md](./PROJECT_STATUS.md) — “complete for daily use”
- [ ] Prune stale items in [TASKS.md](./TASKS.md)

**Optional:** `topic_study_runs` resume/history — only if you miss it while using the app.

---

## Agent rules (cape time)

1. **Verify first** — Sprint 4 before any polish or feature.
2. **Fix breaks only** — if acceptance fails, fix the smallest path; no redesign.
3. **No new lanes** — wearables, Zepp, hard-block, life-clock skins stay as-is unless broken.
4. **Commits** — only when user asks.
5. **Check off** TASK_COMPLETION as proof lands.

---

## File map (quick reference)

| Sprint | Backend | Frontend |
|--------|---------|----------|
| 1 ✅ | `study_flow.py`, `router.py` | — |
| 2 ✅ | — | `TopicStudyFlowPage.tsx`, `transcriptsClient.ts` |
| 3 ✅ | `quiz/handler.py`, `next_step.py`, skills | `StudyLoopWidget`, `GlobalQuizRunner`, Review Hub |
| 4 | tests + health | manual walkthrough |
| 5 | — | empty states, docs |

---

## Related docs

| Doc | Use |
|-----|-----|
| [TASK_COMPLETION.md](./TASK_COMPLETION.md) | Master checklist + definition of done |
| [SESSION_LOG.md](./SESSION_LOG.md) | Per-session progress |
| [PROJECT_STATUS.md](./PROJECT_STATUS.md) | What’s working today |
| [docs/decisions/ADR-001-quiz-practice-orchestration.md](./decisions/ADR-001-quiz-practice-orchestration.md) | Quiz / practice decisions |
| Superpowers plans under `docs/superpowers/plans/` | **Reference only** — not active build queues |
