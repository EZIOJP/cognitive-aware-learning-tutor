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
- Study-flow must resume `?session=` instead of orphaning pre-created sessions.
- Layer 0 ships with the engine; Layers 1–5 are content expansion on the same checker/generator pattern.
