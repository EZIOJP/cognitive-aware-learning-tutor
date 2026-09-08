# Daily Bite Study Loop Implementation Plan

> **For agentic workers:** Use executing-plans. Commits only if the user asks.

**Goal:** One-click daily path: freeze top-2 eligible tags, sequential read→quiz (B) or combined C when all non-stub; after plan confirm, land on `/review?tab=loop`.

**Architecture:** `topic_stub_flags.json` for stub booleans; SQLite `study_loop_days` freeze per user/day; `GET/POST /api/quiz/study-loop/today` drives LoopTab; morning `next=study` until the day’s gated items are attempted once.

**Tech Stack:** FastAPI, SQLAlchemy, existing Study Loop sessions + `/api/quiz` start.

## Global Constraints

- Spec: `docs/superpowers/specs/2026-09-04-daily-bite-study-loop-design.md`
- ADR-001: one quiz engine, one FSRS
- N=2; practice_count from inventory not ReviewCard total
- Done = attempted once; owes may remain
- Default practice count 15 for daily bite
- No curriculum.json ranking

## Files

| Path | Role |
|------|------|
| `backend/quiz/topic_stub_flags.py` | JSON stub flags + lock |
| `backend/quiz/daily_bite.py` | Candidates, score, freeze, state |
| `backend/models/study_loop.py` | `StudyLoopDay` |
| `alembic/versions/0031_study_loop_days.py` | Migration |
| `backend/quiz/study_loop.py` | C bundle read + count 15 from today |
| `backend/quiz/router.py` | GET/POST today |
| `backend/math/curriculum_pass/stubs.py` | Set stub true on create |
| `backend/quiz/note_writeback.py` | Set stub false on edit |
| `backend/behavior/distraction_gate.py` | `next=study` |
| `src/features/quiz/studyLoop/LoopTab.tsx` | Today’s path CTA |
| `src/components/MorningGateRedirect.tsx` | Redirect to loop |
| `tests/test_daily_bite.py` | Spec tests 1–9 |

## Tasks

1. Stub flags + tests
2. Selection + freeze + state + tests
3. Routes + start-practice gated ids
4. Morning next=study + redirect
5. LoopTab one-click UI
6. Wire stub writes on stub-create and note PATCH
