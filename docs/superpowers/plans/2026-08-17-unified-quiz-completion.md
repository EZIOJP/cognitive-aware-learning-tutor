# Unified Quiz Completion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** One `/api/quiz` engine for lecture, math, and vocab → shared Review Hub; notes/quiz rules enforced; productivity tracking visuals polished.

**Architecture:** Extend ADR-001. Bridge legacy GRE adaptive into ReviewCards; keep GlobalQuizRunner as the only product runner for new UX.

**Tech Stack:** FastAPI, SQLAlchemy ReviewCard FSRS, React GlobalQuizRunner, existing productivity calendar components.

## Global Constraints

- No second SRS / quiz runner / home summary brain
- No Study Flow or corpus RAG resurrection
- Commits only when user asks
- Wire don’t migrate

---

### Task 1: Vocab adaptive → ReviewCard bridge

**Files:**
- Modify: `backend/vocab/routes.py`
- Test: `tests/test_vocab_adaptive_review_bridge.py` (create)

- [x] Write failing test: adaptive answer creates/updates `ReviewCard` domain=vocab
- [x] In `quiz_answer` (adaptive), call `upsert_review_card` with word id/label/meaning payload
- [x] Run test green
- [x] Optional: on adaptive complete, ensure hub event still fires

### Task 2: Prefer global vocab quiz from Review / Cycle CTAs

**Files:**
- Modify: `src/pages/quiz/ReviewHubPage.tsx` (Start vocab → `/api/quiz` if not already)
- Modify: `src/features/vocab/cycle/components/CycleQuizStep.tsx` **or** keep Cycle on adaptive if bridge is solid
- Modify: `src/components/dashboard/StudyLoopWidget.tsx` if CTAs still point only at GRE read

- [x] Confirm Review Hub Start vocab uses `globalQuizClient` domain=vocab
- [x] If Cycle stays on adaptive, document that bridge covers SRS
- [x] Manual or unit: backlog due_count includes vocab cards after quiz

### Task 3: Notes → quiz guardrail test

**Files:**
- Modify: `backend/transcripts/` generate-quiz path if needed
- Test: assert `prefer_notes` / seed deck behavior

- [ ] Add/adjust test that library generate-quiz prefers notes and can seed deck
- [ ] Fix only if broken

### Task 4: Mixed daily practice / next_step

**Files:**
- Modify: `backend/quiz/next_step.py`, `daily_practice.py` if vocab due ignored
- Modify: StudyLoopWidget label copy if needed

- [x] Due cards from any domain → `review_due` CTA
- [ ] Test next_step priority still: due → math → notes → vocab

### Task 5: Productivity infographic polish

**Files:**
- `src/components/productivity/PlanVsActualDashboard.tsx`
- `WeeklyAdherenceHeatmap.tsx`
- `CategoryVarianceChart.tsx`
- `GlanceBar.tsx` / empty states on Calendar tab

- [x] Ensure empty/loading states are clear (no blank panels)
- [ ] Streak / adherence readable when data sparse
- [x] No reintroduction of TodayPanel

### Task 6: Verification

- [x] `python -m pytest tests/test_vocab_adaptive_review_bridge.py tests/test_productivity_week_export.py -q`
- [x] Broader `python -m pytest tests/ -q` (725 passed, 3 skipped)
- [x] `npm run build`
- [x] Update `docs/SESSION_LOG.md` + checkmarks in TASK_COMPLETION for verified items
