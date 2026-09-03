# Design: Study Loop / Daily Learn

**Date:** 2026-09-03  
**Status:** Approved (Approach **A** — notes canonical; read cards are a view + edit surface)  
**ADR:** Extends [ADR-001](../../decisions/ADR-001-quiz-practice-orchestration.md)  
**Prior mandate:** [2026-08-17 unified quiz completion](./2026-08-17-unified-quiz-completion-design.md)  
**Brainstorm:** tags-as-stitch; Read → Questions → FSRS; [transcript](../../../../.cursor/projects/c-Users-Lenovo-Desktop-Cognitive-Aware-Learning-Tutor/agent-transcripts/df9cdf3f-07ed-4d35-8ab0-3d6e36811203/df9cdf3f-07ed-4d35-8ab0-3d6e36811203.jsonl)

---

## 1. Problem

Daily Learn (`/review`) today is still a **quiz launcher + FSRS due queue**. The owner wants a **Study Loop**:

1. **Read cards** digested from existing lecture/math notes (`L{n}-Txx`, `MT{n}-Txx`).
2. **Editable** notes via those cards (write back into the markdown file).
3. **Questions** after reading — forced path through practice when in the loop.
4. **Tag stitch** across lecture notes, math notes, vocab, and question banks so one tag gathers read + practice.
5. **CRUD / import** for MCQ, coding, coding-MCQ, and open math; fill answers on no-answer items; Python IDE for coding kinds.

Without this, notes drift from practice, open/no-answer items stay stuck, and domains stay siloed.

---

## 2. Goals

| # | Goal |
|---|------|
| G1 | Digest note sections into editable **read cards** (no second flashcard DB). |
| G2 | **Approach A write-back:** editing a read card patches the note file under `data/notes/`. |
| G3 | Shared **tag** model: add / rename / merge on notes **and** questions; vocab joins via tags/groups. |
| G4 | Study Loop UX: **pick tag → read → practice → due (FSRS)**. Force practice after read when in-loop. |
| G5 | Question CRUD + import (MCQ / coding / coding-MCQ / free math) into existing content bank / decks. |
| G6 | Open/no-answer items editable (add answer, solution_steps, explanation). |
| G7 | Python IDE for coding kinds (reuse `PythonCodeBlock` + wire `code_runner`). |
| G8 | **Wire, don’t migrate:** one `/api/quiz` engine, one `ReviewCard` FSRS (ADR-001). |
| G9 | Surface rename: **Daily Learn / Study Loop** (Review Hub page evolves in place at `/review`). |

---

## 3. Non-goals

- Second SRS, second quiz runner, or `GET /api/home/summary`.
- Restoring Study Flow / live corpus RAG Knowledge Base (notes already on disk are enough for digests).
- Full multi-language IDE (Python only for this epic).
- Migrating GRE Cycle off adaptive shims in one shot (prefer `/api/quiz` domain=`vocab`; keep bridges).
- Rebuilding the entire Review Hub tabs from scratch — evolve Start/Due into Loop + keep decks/results.
- Auto-scraping copyrighted textbooks into the bank.

---

## 4. Principles

1. **Notes canonical** — markdown under `data/notes/` is the source of truth for read content.
2. **Tags = stitch key** — `note_topic_ids` (`L*` / `MT*`) + free tags on questions; vocab via `vocab.group.{n}` + word `tags[]`.
3. **YAGNI / DRY** — reuse `content_bank`, `note_topics`, `review_cards`, `code_runner`, `handler.start_session`, `library.save_note_content`, `GlobalQuizRunner`, `PythonCodeBlock`.
4. **TDD** where backend APIs change.
5. **Minimal diffs** — match existing FastAPI / React patterns; no platform rewrite.
6. **One engine** — practice always ends in `POST /api/quiz/start` → answer → `upsert_review_card`.

---

## 5. Architecture

```text
data/notes/**/*.md          content_bank JSON                 vocab words.json
        │                         │                                  │
        ▼                         ▼                                  ▼
 parse_note_topics()        note_topic_ids + tags            vocab.group.N / tags
        │                         │                                  │
        └──────────────►  Tag Index (union)  ◄───────────────────────┘
                                │
              ┌─────────────────┼─────────────────┐
              ▼                 ▼                 ▼
         Read cards        Questions          Due queue
      (section view)    (bank + decks)     (ReviewCard FSRS)
              │                 │                 │
              │ write-back A    │ CRUD/import     │
              ▼                 ▼                 ▼
         note .md file     data/questions/**   /api/quiz/start
                                                   domain=review|math|study|code|vocab
```

### 5.1 Read-card digest

- Scan `NOTES_DIR` for indexable `.md` (reuse library filters; skip `rules/`).
- For each file, `parse_note_topics(body)` → `NoteTopic(topic_id, title, body, source)`.
- Emit **read cards** (ephemeral views, not a new DB table):

```text
card_id = "{relative_path}::{topic_id}"   # e.g. L05_pandas_operations_notes.md::L5-T05
```

- Fields: `card_id`, `tag` (= topic_id), `title`, `body_markdown`, `note_path`, `source` (`lid`|`decimal`|`heading`), `char_count`, `mtime`.

### 5.2 Practice after read

- Questions for a tag = union of:
  - content_bank items where `tag ∈ topic.note_topic_ids` or `tag ∈ question.tags`
  - live mathgenerator recipes filtered by `note_topic_ids` (already on hybrid catalog)
  - study MCQ decks / generated packs tagged with that topic
  - vocab words whose `tags` contain the tag **or** whose group maps to `vocab.group.{n}` when that is the selected tag
- Starting practice calls existing `handler.start_session` with appropriate `domain` + `config.note_topic_id` / `word_ids` / content filters.

### 5.3 Forced gating

When `mode=study_loop` (session created via Study Loop API):

1. Client cannot call “Start practice” until `mark-read` for that tag’s card(s) in the current loop session.
2. Server rejects `start-practice` with `400` if `read_completed` is false.
3. Escape hatches (not gated): Due tab FSRS review, Flash decks, Create deck — those stay available outside the loop.

---

## 6. Data model

### 6.1 Tag

| Field | Type | Notes |
|-------|------|-------|
| `id` | string | Canonical id. Note topics uppercased (`L5-T05`, `MT1-T02`). Free tags: lowercase `[a-z0-9._-]`. Vocab groups: `vocab.group.{n}`. |
| `kind` | `note_topic` \| `free` \| `vocab_group` | |
| `label` | string | Display title (from Topic Index / note heading / group label). |
| `aliases` | string[] | Optional legacy forms (`LT5.5` → canonical). |
| `note_paths` | string[] | Notes that contain this section. |
| `question_count` | int | From content bank (+ decks when tagged). |
| `vocab_count` | int | Words linked. |
| `has_read_card` | bool | |

**No separate Tag SQLite table in v1** — compute index on demand from notes + catalog + vocab (cache stamp by mtimes). Persist only when needed for free-tag overrides in `data/questions/_tags.json` (optional small sidecar for renames of free tags that aren’t note headings).

### 6.2 NoteSection / ReadCard view

| Field | Type |
|-------|------|
| `card_id` | `"{note_path}::{topic_id}"` |
| `tag` | topic_id |
| `title` | string |
| `body_markdown` | string (section body **without** the `##` heading line) |
| `heading_markdown` | string (exact heading line including `#` marks) |
| `note_path` | relative under `NOTES_DIR` |
| `mtime` | float (disk) |
| `source` | `lid` \| `decimal` \| `heading` |

### 6.3 Question tags

- Topic-level: `ContentTopic.note_topic_ids` (existing).
- Item-level: `MathQuestion.tags` / `CodingQuestion.tags` / MCQ `tags` (existing + extend).
- Study Loop filters: `tag` matches if present in either list (case-normalized for note topics).

### 6.4 Vocab stitch

| Mechanism | Rule |
|-----------|------|
| Default group tag | Every word in group `N` is linked to `vocab.group.N`. |
| Free tags | Word `tags[]` already exists in vocab bank — Study Loop lists them. |
| Attach | `PATCH` word or bulk “add tag to group” adds a free tag / note topic id onto selected words. |
| Practice | `POST /api/quiz/start` domain=`vocab` with `word_ids` or `group_number`. |

### 6.5 StudyLoopSession (SQLite / SQLAlchemy)

Stored as a SQLAlchemy model next to `ReviewCard` (same SQLite DB) — **not** a flat JSON file under `data/behavior/`:

```text
StudyLoopSession
  session_id, user_id, tag, read_completed,
  read_card_ids (JSON list of path::topic_id),
  practice_quiz_session_id, created_at, updated_at
```

Wire don’t migrate: reuse the trusted SQLAlchemy persistence layer for crash-safe session state.

---

## 7. Write-back rules (Approach A)

When `PATCH` read card body/title:

1. Resolve `note_path`; refuse path escape outside `NOTES_DIR`.
2. Require `expected_mtime` (same pattern as `PUT /api/transcripts/library/files/.../content`) → `409` on conflict.
3. Locate section by canonical `topic_id` in headings (`## \`L5-T05\` — …` or `#` ``MT1-T02`` forms).
4. **Preserve** the heading line’s topic id; if `title` changed, rewrite only the title portion after the em-dash.
5. Replace section body until the next heading of level ≤ current — **fence-aware:** ignore heading-looking lines inside fenced code blocks (` ``` ` … ` ``` `).
6. If Topic Index row exists for that id, update its title cell / bullet to match.
7. Run `sanitize_note_content` before write (existing lint).
8. **Atomic write:** temp file + `os.replace()`; optional `STUDY_LOOP_GIT_CHECKPOINT=1` may snapshot before write (default off).
9. Call `library.save_note_content` (or shared helper) so DB index `section_count` / `updated_at` stay coherent.
10. Invalidate via shared `source_stamp.bump_notes()` (all readers check stamps — not ad-hoc per module).

**Must not:** create a parallel card store; duplicate the whole file into SQLite; silently drop fences/mermaid; truncate at `##` inside code fences.

---

## 8. Tag CRUD / rename / merge

| Op | Behavior |
|----|----------|
| **List** | Union of note topics + free tags on questions + vocab groups/tags. |
| **Add (free)** | Attach tag string to selected note section (optional YAML/html comment footer **or** add to Topic Index as free alias — prefer: add to question `tags` and/or word `tags`; for notes, allow `<!-- tags: foo,bar -->` under the section heading, parsed by digester). |
| **Add (note topic)** | Creating a new `L*`/`MT*` section is out of scope for v1 auto-insert; user edits note or uses Lecture Notes structure tools. Study Loop **add** focuses on free tags + linking existing topics to questions/vocab. |
| **Rename** | Note topic rename: rewrite heading ids + Topic Index + **all on-disk** `data/questions/**/*.json` `note_topic_ids` / question `tags` + vocab tags + curriculum `note_topic_id`. Free tag rename: same JSON rewrite + sidecar. Index-only updates are a lock violation. |
| **Merge** | `from_tag` → `into_tag`: rewrite all references to `into_tag` **including question JSON files**, remove `from_tag`. Merging two note topics is **manual note edit** in v1 (API returns `400`). |

Propagation targets:

- `data/notes/**/*.md` (headings / index / `<!-- tags: -->`)
- `data/questions/**/*.json` (`note_topic_ids`, `tags`) — **required for refs_updated**
- `data/questions/math/curriculum.json`
- Vocab word records (`tags`)
- ReviewCard `topic` / payload tags when present (best-effort update; do not break `item_key`)
- Shared `source_stamp.bump_questions()` after JSON rewrites

---

## 8b. Practice domain resolution (before Task 5)

`start_practice` **must not** map every non-vocab tag to `domain=math`. Resolve by inspecting content under the tag (`resolve_practice_route`):

| Condition | `domain` |
|-----------|----------|
| `vocab.group.N` | `vocab` |
| Only math packs / generators | `math` |
| Only coding | `code` |
| Only `mcq` / `coding_mcq` | `study` |
| Mix | `mixed` |
| Empty | error `no_practice_content` (never silent mathgen for `L*`) |
---

## 9. Study Loop UX states

Surface: `/review` (plugin route). Title: **Daily Learn**. Primary flow tab: **Loop** (evolve today’s Learn/Start).

| State | UI | Next |
|-------|----|------|
| `pick_tag` | Tag browser (lecture / math / vocab / free), search, counts | Select tag |
| `read` | Read card markdown (editable), tag chips, “Mark read & practice” | mark-read |
| `practice` | `GlobalQuizRunner` for that tag’s items | complete → due |
| `due` | Existing Due tab / FSRS queue filtered optionally by tag | review |
| `edit_question` | Side panel: CRUD / fill open answer | save → bank |
| `import` | Upload/paste JSON or markdown MCQ list | parse → preview → commit |

Empty states: if tag has read card but 0 questions → CTA “Import / generate / add question”, still allow mark-read then soft-warn. If no read card (vocab-only tag) → skip read gate automatically (`read_completed=true`).

---

## 10. Import formats

Extend authored content contract (`docs/QUESTION_CONTENT_FORMAT.md` + `content_schemas.py`):

| Kind | Shape | Notes |
|------|-------|-------|
| `mcq` | `question`, `options[]`, `answer_index`, optional `explanation`, `hint`, `tags` | New files under `data/questions/mcq/**` **or** append into study decks tagged with `note_topic_ids`. Prefer content-bank files for reusable packs. |
| `math` | existing `MathQuestion` | Empty `answer` ⇒ `answer_format=open` / `no-answer` tag (already). |
| `coding` | existing `CodingQuestion` | Graded by `code_runner.grade_submission`. |
| `coding_mcq` | `prompt`, `options[]`, `answer_index`, optional `starter_code`, `tags` | Multiple-choice over approaches/snippets; IDE optional for free exploration, grade by `answer_index`. |

Import API accepts:

1. Full `ContentFile` envelope (schema_version 1).
2. Bare `questions[]` + `topic_id` / `note_topic_ids` query/body fields.
3. Simple markdown list for MCQ (parser: `Q.` / `A.` / `-` options with `*` correct) — best-effort.

On success: **upsert by question `id`** into existing pack or `data/questions/<kind>/_user/{safe_topic_id}.json` (idempotent re-import), `source_stamp.bump_questions()`, `load_catalog(refresh=True)`, optional `seed_content_cards`.

---

## 11. Open-answer editing

- List questions with `answer_format=open` or empty `expected_answer` / `no-answer` tag.
- `PATCH` allows setting `answer`, `answer_format`, `solution_steps`, `explanation`, `hint` without changing `id`.
- In runner: open items use **self-check** UX (reveal solution; user marks Confident / Still unsure) → still call `upsert_review_card` with `correct` from self-grade (existing handler path for open math).

---

## 12. Python IDE scope

| Context | Tool |
|---------|------|
| Free practice / notes code fences | Existing `PythonCodeBlock` + Pyodide (`runPython`) |
| Authored coding question “Run tests” | Wire missing `POST /api/quiz/code/run` → `code_runner.run_submission` / `grade_submission` |
| Quiz submit | Existing handler path calling `grade_submission` |

v1 IDE panel = enhance `PythonCodeBlock` usage in Study Loop practice + Create/Edit coding forms (starter_code editor + Run tests). No Monaco hard requirement if current block is sufficient; add test-results list for harness output.

---

## 13. Forced read → practice gating

```text
POST /study-loop/sessions          { tag }
  → { session_id, tag, read_cards[], read_completed: false|true }

POST /study-loop/sessions/{id}/mark-read
  → { read_completed: true }

POST /study-loop/sessions/{id}/start-practice  { count?, kinds? }
  → requires read_completed
  → `resolve_practice_route(tag)` → domain by content (not hardcoded math)
  → internally `handler.start_session(domain=route.domain, config=route.config)`
  → { quiz_session_id, question, domain }
  → empty content → 400/404 `no_practice_content`
```

Vocab-only / question-only tags: auto `read_completed=true` when `has_read_card=false`.

---

## 14. API sketch

All under `/api/quiz` (auth: current user), unless noted.

### Tags

| Method | Path | Body / query | Response |
|--------|------|--------------|----------|
| GET | `/study-loop/tags` | `?q=&kind=` | `{ tags: TagSummary[] }` |
| POST | `/study-loop/tags` | `{ id, attach?: { note_path, topic_id } \| { question_id } \| { word_ids } }` | TagSummary |
| PATCH | `/study-loop/tags/{tag}` | `{ new_id, label? }` | `{ renamed, refs_updated }` |
| POST | `/study-loop/tags/merge` | `{ from_tag, into_tag }` | `{ merged, refs_updated }` |

### Read cards

| Method | Path | Notes |
|--------|------|-------|
| GET | `/study-loop/read-cards?tag=` | List digests for tag (may be multi-file). |
| GET | `/study-loop/read-cards/{card_id}` | `card_id` URL-encoded `path::tag`. |
| PATCH | `/study-loop/read-cards/{card_id}` | `{ title?, body_markdown, expected_mtime }` → write-back A. |

### Questions

| Method | Path | Notes |
|--------|------|-------|
| GET | `/study-loop/questions?tag=&kind=` | Normalized items + `open` flag. |
| POST | `/study-loop/questions` | Create one question in bank file (or new file). |
| PATCH | `/study-loop/questions/{id}` | Update fields incl. open answers; rewrite JSON. |
| DELETE | `/study-loop/questions/{id}` | Remove from file; do not delete ReviewCards automatically (orphan ok / soft). |
| POST | `/study-loop/questions/import` | Parse + write pack; return preview errors. |

### Loop session + code

| Method | Path | Notes |
|--------|------|-------|
| POST | `/study-loop/sessions` | Start loop for tag. |
| POST | `/study-loop/sessions/{id}/mark-read` | Gate unlock. |
| POST | `/study-loop/sessions/{id}/start-practice` | Starts real quiz session. |
| GET | `/study-loop/sessions/{id}` | Status. |
| POST | `/code/run` | **New route** (doc already claims it): `{ item_id? \| item, code }` → test outcomes. |

Existing routes remain: `/start`, `/content/catalog`, `/content/import`, `/review/due`, `/backlog`.

---

## 15. Frontend

| Piece | Path |
|-------|------|
| Page evolve | `src/pages/quiz/ReviewHubPage.tsx` — add **Loop** tab; keep Due / Decks / Create / Results |
| Client | `src/api/globalQuizClient.ts` — study-loop + code/run helpers |
| Read panel | `src/features/quiz/studyLoop/ReadCardPanel.tsx` |
| Tag picker | `src/features/quiz/studyLoop/TagPicker.tsx` |
| Question editor | `src/features/quiz/studyLoop/QuestionEditor.tsx` |
| Runner | Reuse `GlobalQuizRunner` |
| IDE | Reuse/enhance `PythonCodeBlock`; show harness results from `/code/run` |
| Widget | `StudyLoopWidget` CTA → `/review?tab=loop` |

Copy: “Daily Learn” brand; subtitle “Study Loop — read, practice, remember”.

---

## 16. Acceptance criteria

1. Selecting `L5-T05` shows a read card whose body matches the note section; editing + save updates `L05_pandas_operations_notes.md` on disk (mtime/409 conflicts work).
2. Selecting `MT1-T02` shows math note digest and lists content_bank / generator questions with that `note_topic_id`.
3. Study Loop blocks practice until mark-read when a read card exists; vocab-only tags skip gate.
4. Tag rename of a free tag rewrites question JSON tags; merge free→note topic works; illegal note↔note merge returns clear 400.
5. Import MCQ + coding + coding_mcq + open math succeeds; open items editable to add answers.
6. Coding practice: Run tests via `/api/quiz/code/run`; submit still grades through `/api/quiz/{id}/answer`.
7. Completing practice upserts `ReviewCard`s; Due tab shows them (no second SRS).
8. Vocab group tag `vocab.group.1` starts domain=`vocab` quiz for that group.
9. `python -m pytest tests/test_study_loop*.py tests/test_quiz_content_bank_api.py tests/test_note_topics.py -q` green; `npm run build` green.
10. No Study Flow / corpus RAG resurrection; no `/api/home/summary`.

---

## 17. Migration / rollout

| Step | Action |
|------|--------|
| 0 | Ship APIs behind existing `/review` UI gradually (Loop tab). |
| 1 | Digests are computed — **zero** data migration for notes. |
| 2 | Question CRUD writes the same `data/questions/**` tree already loaded by catalog. |
| 3 | Existing ReviewCards untouched; new practice continues to seed via `seed_content_cards` / `upsert_review_card`. |
| 4 | Curriculum JSON continues to drive Math Daily Path; Study Loop tags align with `note_topic_id`s already present. |
| 5 | Feature flag optional: `studyLoop.enabled` in frontend config default **true** for local-first owner. |
| 6 | Docs: SESSION_LOG entry + link from AGENTS.md “current focus” when implementing. |

**No data loss:** write-back uses mtime checks; imports create/merge files; deletes of questions are explicit; tag merge is transactional per file (write temp then replace).

---

## 18. Risks & open ambiguities (resolved in plan where possible)

| Risk | Mitigation |
|------|------------|
| `POST /api/quiz/code/run` documented but **not** on router | Task wires it. |
| Lecture MCQs live in decks, not content_bank | Import/create prefers `data/questions/mcq/`; decks remain for custom quizzes. |
| Vocab “tags” vs groups | Normalize `vocab.group.N` + free `tags[]`. |
| Note topic merge | Disallow automatic section merge in v1. |
| Math notes short vs lecture notes long | Same digester; empty body → no card / soft empty state. |
| `coding_mcq` schema gap | Extend `content_schemas` + CONTENT_KINDS. |

---

## 19. Implementation plan

See [docs/superpowers/plans/2026-09-03-study-loop.md](../plans/2026-09-03-study-loop.md).
