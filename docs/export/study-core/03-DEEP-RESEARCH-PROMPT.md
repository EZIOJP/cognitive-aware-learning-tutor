# Google Deep Research / Gemini Deep Research — Study Core Prompt

## How to use

1. **Paste this entire file** into Google Deep Research (or Gemini Deep Research).  
2. Optionally **attach** `01-ARCHITECTURE-AND-STUDY-LOOP.md` and `02-NOTES-QUESTIONS-EXAMPLE.md` from the same folder for richer grounding.  
3. If the tool allows **only one file**, this file alone is enough — it embeds a condensed architecture appendix below.  
4. Ask the research run to **prioritize actionable redesigns** mapped to the file/API layout (not generic edtech fluff).

**Product scope of this research:** local-first study notes, quiz, vocab, math, Study Loop / FSRS.  
**Exclude:** productivity desktop trackers, distraction-blocking/gate systems, wearables, ritual planners.

---

## Research prompt (copy from here)

You are researching improvements for **Cognitive-Aware Learning Tutor (CALT)**, a local-first personal study app. Below is the system architecture as implemented / designed. Produce **concrete, prioritized recommendations** tied to this layout — not generic advice.

### System in one page

CALT’s learning core is:

```text
Markdown notes (data/notes/)
  → topic IDs L{n}-Txx (lecture) and MT{n}-Txx (math)
  → authored / generated questions (data/questions/** JSON + hybrid math generators)
  → ONE quiz engine: POST /api/quiz/start → answer → complete
  → ONE spaced-repetition store: ReviewCard + FSRS (SQLAlchemy / SQLite)
  → Daily Learn UI at /review (Review Hub)
```

**Stack:** React 18 + Vite + TypeScript frontend → FastAPI (`backend/main.py`) → SQLite `data/vocab_app.db` + on-disk notes/questions/vocab JSON.

**Domains of practice:** `study` (lecture MCQ/decks), `math` (curated bank + mathgenerator + skill Layer 0 / SymPy), `vocab` (GRE `public/data/words.json`, prefer `/api/quiz` domain=vocab), `code`/`coding` (Python harness in `code_runner.py`), `review` (due FSRS queue), `deck`.

**Architectural locks (ADR-001):**

- Do **not** add a second SRS or second quiz runner.  
- Do **not** add `GET /api/home/summary` as a competing “what’s next” brain — use `/api/quiz/backlog` → `next_step`.  
- Wire features into existing handlers; don’t migrate to a new platform.  
- Math free-text answers graded with **SymPy equivalence**, not LLM-guessed keys.  
- Notes are canonical for read content; quizzes should prefer note-grounded generation.

**Tag stitch:** Questions declare `topic.note_topic_ids` (e.g. `["MT1-T02"]`) plus free `tags[]`. Study Loop (approved, Approach A) digests note sections into ephemeral **read cards** (`path::topic_id`), lets users **edit with write-back into the .md file**, forces **read → practice** when in the loop, and unions tags across notes + question bank + vocab groups (`vocab.group.N`). Practice still calls `handler.start_session` and upserts ReviewCards.

**Study Loop UX states:** pick_tag → read (editable) → mark-read → practice (`GlobalQuizRunner`) → due (FSRS). Vocab-only tags skip the read gate. Planned APIs live under `/api/quiz/study-loop/*` plus `POST /api/quiz/code/run`.

**Known gaps:** lecture topics often lack reusable content-bank MCQ packs; open/no-answer olympiad items need fill-in workflows; `/code/run` route may be documented but not wired; Daily Learn is still mostly a quiz launcher until Study Loop ships; note→quiz grounding quality varies.

### What to research and recommend

Evaluate and suggest improvements on:

1. **Spaced repetition UX** — FSRS due queues in study apps; topic packs vs per-item cards; how to surface “Daily Learn” without overwhelming; anti-patterns (too many due, burying weak concepts).  
2. **Tag-based curriculum stitching** — using stable topic IDs (`L*`/`MT*`) + free tags to unite notes, questions, and vocab; rename/merge strategies; comparable products (Anki tags/decks, RemNote, Quizlet, SuperMemo, Memrise, Brilliant, Khan, etc.).  
3. **Note → quiz grounding quality** — how high-quality systems keep questions faithful to a note section; linting; coverage metrics; human-in-the-loop authoring.  
4. **Math hybrid banks** — combining curated closed-form items, procedural generators, and open/proof items; when to use self-check vs auto-grade; SymPy-style grading literature.  
5. **Forced read → practice Study Loops** — evidence for “read then retrieve” gating; escape hatches; when forcing backfires.  
6. **Open-answer / proof workflows** — self-grading UI, rubrics, partial credit, LLM-as-judge risks for math.  
7. **Coding MCQ + in-browser Python IDE** — coding-MCQ patterns; Pyodide vs server harness; showing test outcomes; security for local-first.  

Also identify: **comparable products**, **key papers / reviews** (retrieval practice, spaced repetition, worked examples, desirable difficulties), **anti-patterns**, and **redesign ideas that fit CALT’s file/API map**.

### Constraints the recommendations must respect

- Local-first / personal (not multi-tenant SaaS assumptions).  
- One `/api/quiz` engine and one ReviewCard FSRS.  
- Notes under `data/notes/` remain source of truth for read text (Approach A write-back).  
- Prefer extending: `backend/quiz/*`, `backend/transcripts/note_topics.py`, `content_bank.py`, `ReviewHubPage` / Study Loop tab.  
- Do not recommend resurrecting a separate corpus-RAG “Study Flow” as the primary path unless clearly superior *and* compatible with the ADR locks.  
- Ignore productivity tracking and distraction-blocking product lines.

### Evaluation criteria

Score each recommendation on:

| Criterion | Meaning |
|-----------|---------|
| Impact | Learning outcomes / retention / daily adherence |
| Fit | Compatibility with one-engine + notes-canonical architecture |
| Effort | S / M / L relative to a solo maintainer |
| Evidence | Paper / product precedent strength |
| Risk | Regression, content drift, UX friction |

### Desired output format

Return a report with:

1. **Executive summary** (≤12 sentences).  
2. **Comparable products & what to steal** (table: product → feature → CALT mapping).  
3. **Research highlights** (5–10 citations or named papers/reviews with one-line takeaway each).  
4. **Prioritized recommendations** (ranked list). For each:  
   - Title  
   - Problem it solves in CALT  
   - Proposed change (UX and/or backend)  
   - Map to files/APIs (e.g. `study_loop.py`, `content_schemas.py`, `/study-loop/tags`, `GlobalQuizRunner`)  
   - Effort / Impact / Evidence / Risk  
   - Acceptance test idea  
5. **Anti-patterns to avoid** (bullet list).  
6. **90-day roadmap** for a solo builder already mid Study Loop plan (Tasks 1–9): what to prioritize first after the gate/read/CRUD MVP.  
7. **Open questions** needing owner judgment (≤8).

Be specific. Prefer recommendations that improve **tag stitch**, **grounding**, **open answers**, **coding IDE**, and **SRS UX** inside the existing architecture.

---

## Condensed architecture appendix (self-contained)

### Entry points

- Frontend: `src/main.tsx` → App → Review Hub `src/pages/quiz/ReviewHubPage.tsx`  
- API: `backend/main.py`, quiz router `backend/quiz/router.py` prefix `/api/quiz`  
- Paths: `NOTES_DIR=data/notes`, `QUESTIONS_DIR=data/questions`, GRE `public/data/words.json`

### Domain paths

| Domain | Backend | Data |
|--------|---------|------|
| Notes | `backend/transcripts/` (`note_topics.py`, generators, library) | `data/notes/**/*.md` |
| Quiz/SRS | `backend/quiz/handler.py`, `review_cards.py`, `srs.py` | SQLite ReviewCard |
| Content bank | `content_bank.py`, `content_schemas.py` | `data/questions/{math,coding}/**` |
| Math hybrid | `math_generators.py`, `backend/math/` | generators + bank + MT notes |
| Vocab | quiz domain=`vocab`; legacy `/api/vocab/...` | `words.json` |
| Coding | `code_runner.py` | coding JSON + planned `/code/run` |

### Topic IDs

- Lecture: `L5-T05` in headings `## \`L5-T05\` — title`  
- Math: `MT1-T02` similarly  
- Canonicalize: `l5-t5` → `L5-T05` via `canonicalize_topic_id`  
- Read card id: `{relative_note_path}#{topic_id}`

### Data flow

```text
note.md → parse_note_topics → (future) read card view
                ↘ study quiz gen / decks
data/questions/*.json → load_catalog → build_quiz_items(note_topic_id=…)
                ↘ handler.start_session(domain=math|…)
answer → upsert_review_card (FSRS) → /review Due
```

Study Loop: `pick tag → read → mark-read → start-practice → FSRS`.

### Example stitch

- Note: `data/notes/math/MT1_aptitude_interview_notes.md` section `MT1-T02` (LCM & HCF).  
- Questions: `data/questions/math/generated/gen-lcm.json` with `"note_topic_ids": ["MT1-T02"]`.  
- Start: `POST /api/quiz/start` `{ "domain": "math", "config": { "note_topic_id": "MT1-T02", "count": 5 } }`.

### Planned Study Loop modules

`read_cards.py`, `note_writeback.py`, `tag_index.py`, `question_crud.py`, `study_loop.py`; frontend `src/features/quiz/studyLoop/*`.

### Implementation tasks already planned (do not reinvent)

1 Digest read cards · 2 Write-back · 3 Tag CRUD · 4 Question CRUD/import + mcq/coding_mcq · 5 Session gate · 6 Vocab tags · 7 Loop UI · 8 `/code/run` · 9 Verify pytest + build.

### Improvement themes for researchers to expand

Coverage of lecture MCQs in content bank; open-answer fill UX; grounding lints; SRS due UX; coding IDE feedback; tag merge/rename safety; metrics for “notes without questions” and “questions without notes.”

---

*End of Deep Research pack. Companion files: `01-ARCHITECTURE-AND-STUDY-LOOP.md`, `02-NOTES-QUESTIONS-EXAMPLE.md`.*
