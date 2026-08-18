# Design: Unified Quiz + Notes Rules + Productivity Polish

**Date:** 2026-08-17  
**Status:** Approved by user (choice 1 + full autonomy while away)  
**ADR:** Extends [ADR-001](../../decisions/ADR-001-quiz-practice-orchestration.md)

## Goal

One shared quiz engine with subject modes (**study / math / vocab**) feeding one FSRS Review Hub queue, plus enforceable notes/quiz generation rules and finished productivity tracking visuals.

## Non-goals

- Restoring Study Flow / corpus RAG Knowledge Base
- New SRS engine, second quiz runner, or `/api/home/summary`
- Wearables / hard-block expansion
- Math OCR Phase 3c / hardware

## Architecture (chosen)

**One engine:** `POST /api/quiz/*` + `ReviewCard` FSRS (`backend/quiz/`).

| Mode | Content source | Session domain | Lands in Review Hub |
|------|----------------|----------------|---------------------|
| Lecture notes | `study_intel.generate_quiz_items` / deck seed | `study` | Yes |
| Math drills | skills generators / bank + SymPy | `math` | Yes (`srs_bridge` + quiz handler) |
| GRE vocab | word bank meanings | `vocab` | Yes via `/api/quiz` (must also bridge legacy adaptive) |

**Dashboard brain remains** `GET /api/quiz/backlog` → `next_step` → `StudyLoopWidget`.

### Vocab unification (gap to close)

- Canonical path already records FSRS: `_submit_vocab` in `handler.py`.
- GRE Cycle still uses `/api/vocab/quiz/adaptive/*`, which updates `WordProgress` only.
- **Fix:** (1) Bridge adaptive answer/complete → `upsert_review_card`, and (2) prefer `/api/quiz` domain=`vocab` from Cycle / Review Start when practical. Keep adaptive routes as compatibility shims.

### Mixed review

- `domain=review` already pulls due cards across domains.
- Daily practice nudge should prefer `/review?tab=due` when any domain has due cards.

## Notes generation rules

Canonical path: Lecture Notes / Studio → `backend/transcripts/note_generation.py` → prompts in `notes_generator.py` + post-processors.

**Policy (enforce in code + Cursor rules):**

1. Transcript-grounded only — no invented lecture facts.
2. Prefer structured markdown (headings, lists, code fences, mermaid only when useful).
3. Repair/lint after generate (`note_lint`, fence repair, mermaid fix paths).
4. Do not resurrect live corpus RAG as default (stubs stay stubs unless user reopens).
5. Quiz generation must prefer notes content (`prefer_notes=True`) and seed a deck when UI asks.

## Quiz generation rules

1. All new quiz UX uses `GlobalQuizRunner` + `/api/quiz`.
2. Domains: `study` | `math` | `vocab` | `review` | `deck` | `code` | `mixed`.
3. Every graded answer that represents lasting knowledge must `upsert_review_card`.
4. Math answers graded by SymPy equivalence — no LLM-guessed keys.
5. Lecture quiz ≥5 items when notes support it; miss → weak-topic / due boost.

## Productivity tracking polish

Keep Calendar-first UX (no Today panel). Finish lagging visuals:

1. Plan-vs-actual dashboard empty/loading clarity
2. Weekly adherence heatmap + streak readability
3. Category variance / day ribbon empty states
4. GlanceBar truthfulness (sleep, due reviews, browser mode)
5. Export already includes wearables — leave as-is unless broken

## Phases

| Phase | Deliverable | Done when |
|-------|-------------|-----------|
| 0 | AGENTS.md + this spec + Cursor rules | Agents follow new mandate |
| 1 | Vocab adaptive → ReviewCard bridge + Cycle/Review CTAs | Vocab answers appear in `/review` |
| 2 | Notes/quiz generation guardrails + tests | Policy tests green; generate-quiz seeds deck |
| 3 | Mixed daily practice / StudyLoop copy | One CTA to Review Hub for all domains |
| 4 | Productivity infographic polish | Empty states + visual QA on Calendar tab |
| 5 | Verify | pytest core + `npm run build` + A5 checklist notes |

## Acceptance

1. From Lecture Notes: generate notes → quiz → complete → due cards on `/review`.
2. From Math Start: drill → answers enqueue math review cards.
3. From GRE Cycle quiz: answers create/update `domain=vocab` ReviewCards (not only WordProgress).
4. Home shows “Review N due” across domains.
5. Productivity Calendar shows clear plan/actual/adherence visuals with empty states.
6. `python -m pytest tests/ -q` (core) and `npm run build` pass.

## Files to touch (primary)

- `AGENTS.md`, `docs/COMPLETION_SPRINT.md`, `docs/PROJECT_STATUS.md`, `docs/SESSION_LOG.md`
- `.cursor/rules/notes-generation.mdc`, `.cursor/rules/quiz-generation.mdc`
- `backend/vocab/routes.py` (adaptive → ReviewCard)
- `backend/quiz/handler.py` / `next_step.py` / `daily_practice.py` as needed
- `src/features/vocab/cycle/*`, `src/pages/quiz/ReviewHubPage.tsx`, `StudyLoopWidget.tsx`
- `src/components/productivity/*` empty states / heatmap polish
- Tests under `tests/test_*quiz*`, `tests/test_*review*`, productivity visuals unit tests
