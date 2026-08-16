# Topic-wise notes quiz + data_foundations Implementation Plan

> **For agentic workers:** Implement task-by-task. Checkboxes track progress.

**Goal:** Canonical `L{n}-Txx` topic notes under `data/notes/data_foundations/`, topic-wise quiz gen → combine → QuizDeck/ReviewCard with note+topic tags, strip stub dashboard widgets.

**Architecture:** Parse note topics (L-IDs primary, decimal fallback) → generate per topic → merge questions tagged with `topic_id`/`note_path`/`hint` → seed existing FSRS via `QuizDeck` + `seed_deck_cards`. No second SRS. Legacy paths `lecture_N/...` resolve to `data_foundations/lecture_N/...`.

**Tech Stack:** FastAPI, SQLAlchemy ReviewCard/QuizDeck, React Lecture Notes UI, existing `study_intel.generate_quiz_items`.

## Global Constraints

- One SRS only (ADR-001)
- Canonical topic IDs: `L{n}-Txx`; decimal `N.M` is fallback only
- Minimal diffs; do not expand Tagged Daily Practice engine

---

## Tasks

- [x] 1. Move `lecture_2..5` → `data/notes/data_foundations/` + legacy path remap
- [x] 2. Topic parser + skip meta sections; tests
- [x] 3. `generate-quiz` topic_ids / by_topic + auto-seed deck with tags
- [x] 4. Lecture Notes quiz UX: topic list → generate → take
- [x] 5. Remove Community + Focus Mirror hint widgets; fix Study Time fake copy
- [x] 6. Verify tests / path remaps
