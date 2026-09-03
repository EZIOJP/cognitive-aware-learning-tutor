# Tag importance + Learning-phase Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Editable tag importance (1–5) with bar + FSRS density, persisted Learning debt, Low Mastery drill, recycle-on-any-queue.

**Architecture:** `data/quiz/tag_importance.json` is the sole importance store (file lock on write only). Cards keep `owes_corrects` in `ReviewCard.srs_json`. Grade path branches: `owes_corrects > 0` → recycle event; else full FSRS + density. Progress / Low Mastery use Study Loop tag stitch.

**Tech Stack:** FastAPI, SQLAlchemy ReviewCard, existing `backend/quiz/srs.py`, React Flash decks / Loop.

## Global Constraints

- Spec: `docs/superpowers/specs/2026-09-04-tag-importance-learning-design.md`
- ADR-001: one `/api/quiz`, one ReviewCard FSRS
- Importance never copied onto card payloads
- `SrsState.mastery` int; bar table 1→2 … 5→6; default importance 3
- Density: interval × factor(max tags) on **full** grades only
- Progress: tag T’s own bar; linkage = `note_topic_ids` + question tags + vocab groups
- Recycle-correct/fail while owing: no `schedule_after_answer`
- Entry fail (owes was 0, post-fail below bar): full fail grade + `owes_corrects = 2`
- Any queue: `owes_corrects > 0` ⇒ recycle processing
- Regen math: ephemeral, never write `data/questions/math/**`
- Suggest: lock write-only; never overwrite `user`; invalid rows listed, partial apply
- Low Mastery start `count` default 15, clamp 1–40
- PUT never-set: omit/null `expected_updated_at`
- Commits only when the user asks (include commit steps for later)

---

## File structure map

| Path | Responsibility |
|------|----------------|
| `backend/quiz/importance.py` | Tables, store I/O + lock, GET/PUT, progress, low-mastery, queue score |
| `backend/quiz/srs.py` | `owes_corrects`; recycle apply; `is_due` includes debt |
| `backend/quiz/review_cards.py` | Due list includes debt; optional recycle upsert helper |
| `backend/quiz/handler.py` | Submit: recycle vs full grade; session reinsert 3–7; math regen ephemeral |
| `backend/quiz/router.py` | Importance routes (low-mastery before `{tag}`) |
| `src/api/globalQuizClient.ts` | Client helpers |
| `src/features/quiz/FlashDecksPanel.tsx` | Importance control + Low Mastery |
| `tests/test_quiz_importance.py` | Store, progress, density, 409 |
| `tests/test_quiz_learning_recycle.py` | Debt, recycle, Due path, regen not persisted |

---

### Task 1: Importance store + tables + lock

**Files:** Create `backend/quiz/importance.py`; Test `tests/test_quiz_importance.py`

**Produces:** `BAR`, `INTERVAL_FACTOR`, `load_store`, `put_importance`, `importance_for`, `bar_for`, `effective_importance`, `file_lock`

- [ ] Tests: default 3; PUT user; stale 409; never-set omit succeeds
- [ ] Implement JSON store + exclusive lock around RMW
- [ ] Run pytest `tests/test_quiz_importance.py`

### Task 2: SRS debt + due

**Files:** Modify `backend/quiz/srs.py`, `review_cards.py`

**Produces:** `SrsState.owes_corrects`; `apply_recycle_answer`; `is_due` true if owes > 0

- [ ] Tests: recycle correct does not change interval; fail while owing resets to 2; is_due with future due_date and owes=1
- [ ] Implement

### Task 3: Progress, Low Mastery API, density on full grade

**Files:** `importance.py` progress/low-mastery; `handler`/`review_cards` density; `router.py`

- [ ] Multi-tag: density max vs progress own bar
- [ ] GET `/importance`, `/{tag}`, `/low-mastery` before `{tag}`
- [ ] PUT with expected_updated_at
- [ ] Full grade applies interval factor

### Task 4: Submit recycle everywhere + queue reinsert + ephemeral math regen

**Files:** `handler.py`

- [ ] `owes_corrects > 0` on Due submit = recycle
- [ ] Entry fail sets owes=2 after full FSRS
- [ ] Reinsert 3–7 in session items list
- [ ] Math regen in payload only

### Task 5: Low Mastery start + queue sort + suggest + UI

**Files:** router start; `globalQuizClient.ts`; `FlashDecksPanel.tsx`

- [ ] POST start count default 15
- [ ] Sort `I * (1 + days_overdue)`
- [ ] Suggest partial apply + dropped_invalid detail (mock LLM)
- [ ] UI: slider, source badge, Low Mastery list + Drill weak

### Task 6: Docs pointer

**Files:** Spec already approved; optional SESSION_LOG skip unless asked
