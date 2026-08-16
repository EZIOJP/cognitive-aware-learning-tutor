# ADR-001: Quiz & practice orchestration

## Status

Accepted

## Date

2026-07-17

## Context

We need a sticky study loop: notes quizzes, vocab, gated math fluency drills, and a clear “what’s next” action. A Downloads-side plan proposed `GET /api/home/summary` as the decision brain, a math skill tree with SymPy grading, and a home widget. The repo already has `GET /api/quiz/backlog`, multi-item quiz sessions (`payload.items`), FSRS `ReviewCard`s, a math question bank, and an OCR/whiteboard tutor path.

## Options Considered

### Option A: New `/api/home/summary` decision brain

- Pros: One Home round-trip
- Cons: Duplicates `backlog_summary`; fights COMPLETION_SPRINT (StudyLoop owns backlog)

### Option B: Extend `/api/quiz/backlog` + `complete_session` with structured `next_step`

- Pros: Reuses ownership; StudyLoop already wired; no second priority engine
- Cons: Home still multi-fetches life stats (acceptable)

### Option C: Thin hub BFF that re-decides priority

- Pros: One payload later
- Cons: Easy to fork logic unless it only embeds backlog

## Decision

We chose **Option B** (backlog-first `next_step`).

Additional locked choices for this epic:

1. **Math multi-question drills** use existing quiz `payload.items` (`domain=math` + `count` / `node_id`), not a new session table. Legacy single-problem `payload.problem` remains for old sessions only.
2. **Skill tree** is a directed graph (JSON catalog first); mastery = last 20 attempts @ ≥85%. Mastered nodes feed existing FSRS review — no second SRS.
3. **Three content lanes:** SymPy procedural generators (fluency); curated `MathQuestion` bank import (complex closed-form); OCR/whiteboard tutor (stuck on hard / non-auto-gradable). No automated copyrighted textbook scrape into the drill bank. Corpus textbooks stay for notes RAG.
4. **SymPy** grades free-text equivalence and computes generator ground truth. Do not LLM-guess math answers.
5. **Start-from-content** lives on Review Hub Start tab (pick Math node or Notes → `POST /api/quiz/start`). No tutor chat inside the quiz runner.
6. **Notes quiz cache** = `QuizDeck` + `seed_deck_cards`, not a parallel store.

## Consequences

- Orchestration stays in `backend/quiz/`; generation stays domain-specific (`math` generators, notes LLM once, vocab bank).
- Insights coach `next_steps[]` remains separate from quiz `next_step`.
- Study-flow / Lecture Notes handoff must resume `?session=` (Review Hub) or embed `GlobalQuizRunner` with `navigateOnComplete={false}` — never orphan a pre-created session.
- Layer 0 ships with the engine; Layers 1–5 are content expansion on the same checker/generator pattern.

## Implementation map (shipped)

| Piece | Location |
|-------|----------|
| SymPy free-text grade | `backend/math/answer_grade.py` → quiz `_submit_study` math + vocab practice submit |
| Multi-Q math start | `handler.start_session` `domain=math` → `payload.items` (`pick_n_from_bank` or `generate_drill_items`) |
| Layer 0 catalog + generators | `backend/math/skills.json`, `skills.py`, `generators/layer0.py` |
| `next_step` brain | `backend/quiz/next_step.py` → `backlog_summary` + `complete_session` |
| Home practice strip | `StudyLoopWidget` primary Next + Notes · Vocab · Math · Review |
| Session resume | `ReviewHubPage` `?session=` / `?math_node=`; `GlobalQuizRunner` `sessionId` + `navigateOnComplete` |

## Follow-up: Layers 1–5 (content-only)

Engine is frozen: JSON node → `generator` name → `generate_for_node` → SymPy `expected_answer` → `answers_equivalent` → `MathAttempt` (topic = skill id) → mastery window in `skills.py` → FSRS via existing review enqueue.

**Do not** add a second SRS, a second quiz runner, or `/api/home/summary`. Expand by adding nodes to `skills.json` with `layer: 1..5` and matching generators under `backend/math/generators/` (same `_base` / SymPy pattern as Layer 0).

Suggested content lanes (not blocking this ADR):

| Layer | Theme (examples) |
|-------|------------------|
| 1 | Linear equations, inequalities, simple word problems |
| 2 | Quadratics / factoring fluency |
| 3 | Exponents & radicals (beyond Layer 0 powers) |
| 4 | Trig basics (unit-circle values) |
| 5 | Sequences / series intro |

Mastery gating UI + Alembic `math_skills` / `MathAttempt.skill_id` remain optional when we outgrow JSON + `topic == skill_id`.
