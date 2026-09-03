# Study Loop — implementation plan for Claude

**Status:** Approved plan condensed for implementation. **None of Tasks 1–9 are implemented in the repo yet** — treat checkboxes as work remaining.  
**Full in-repo plan:** `docs/superpowers/plans/2026-09-03-study-loop.md`  
**Spec:** `docs/superpowers/specs/2026-09-03-study-loop-design.md`  
**Revision:** 2026-09-03 pre-Task-5 locks (content-inspected domain routing, JSON rewrite on rename/merge, fence-aware write-back, atomic IO, shared stamps, idempotent import, `_user` pack paths).

This file is self-contained enough to implement Study Loop together with `01-COMPLETE-OVERVIEW.md` and `02-NOTES-QUESTIONS-AND-SCHEMAS.md`.

---

## Goal & constraints

**Goal:** Daily Learn on `/review`: digest editable read cards from notes (Approach A write-back), stitch tags across lecture/math/vocab/questions, force read→practice, CRUD/import questions, Python IDE via `/api/quiz/code/run` — all on **one** `/api/quiz` + ReviewCard FSRS.

**Locks:**

- Approach **A**: read-card edits write into `data/notes/**/*.md`.
- One engine / one FSRS (ADR-001). No `/api/home/summary`. No Study Flow RAG.
- Wire, don’t migrate. TDD for every new backend API. Python-only IDE this epic.
- Commits only when the user asks.

### Pre-Task-5 locks (do not implement Task 5 without these)

1. **`resolve_practice_route(tag)`** — inspect bank content; never `else → domain=math` (breaks `L5-T05`).
2. **`rename_tag` / `merge_tags` rewrite `data/questions/**/*.json`** (`note_topic_ids` + item `tags`) as part of `refs_updated`.
3. **Fence-aware** section boundary (ignore `##` inside code fences); fixture required for Task 2.
4. **Atomic writes** (`temp` + `os.replace`); optional `STUDY_LOOP_GIT_CHECKPOINT=1` (default off).
5. **Shared `source_stamp`** for notes/questions — one invalidation point for readers.
6. **Imports upsert by `id`** (idempotent); CRUD files live under `data/questions/{kind}/_user/{safe_topic_id}.json`.
7. **ADR math lanes ≠ 5-step hybrid:** three product lanes (SymPy generators · curated bank · OCR/whiteboard). The 5-step order is **only** inside `domain=math` curated+generator resolution. OCR is out of Study Loop Tasks 1–9.
8. **`card_id` = `{posix_path}::{topic_id}`** — never `#` (URL fragment). Encode path segments with `encodeURIComponent` in Task 7.
9. **Study Loop sessions in SQLite** (SQLAlchemy next to ReviewCard) — not a flat JSON file.
10. **409 UX:** toast + keep draft; Reload latest vs Overwrite anyway.
11. **Digester:** skip+log bad notes/topics; do not 500 the whole list.
12. **Answers unit-free** for SymPy grading (units in problem text / display `unit` field only).

---

## File map (create / touch)

| Path | Responsibility |
|------|----------------|
| `backend/quiz/read_cards.py` | Digest note sections → ReadCard views |
| `backend/quiz/note_writeback.py` | Fence-aware patch; atomic write; mtime |
| `backend/quiz/atomic_io.py` | `atomic_write_text` |
| `backend/quiz/source_stamp.py` | notes/questions mtime stamps |
| `backend/quiz/tag_index.py` | List/add/rename/merge (**rewrites JSON on disk**) |
| `backend/quiz/question_crud.py` | CRUD/import under `{kind}/_user/` |
| `backend/quiz/study_loop.py` | Gate + `resolve_practice_route` + practice |
| `backend/quiz/content_schemas.py` | Add `mcq` + `coding_mcq` |
| `backend/quiz/content_bank.py` | Load new kinds; stamp-aware refresh |
| `backend/quiz/router.py` | Mount study-loop + `/code/run` |
| `tests/test_study_loop_*.py` | TDD incl. fence + domain + JSON rewrite |
| `src/features/quiz/studyLoop/*` | Loop UI |
| `docs/QUESTION_CONTENT_FORMAT.md` | New kinds + `_user` packs |

---

## Task 1 — Read-card digester + GET APIs

**Contracts:** `make_card_id` / `parse_card_id` / `list_read_cards(tag=, root=)` / `get_read_card(card_id, root=)`.  
**Routes:** `GET /study-loop/read-cards`, `GET /study-loop/read-cards/{card_id:path}`.  
**Acceptance:** Fixture `L5-T05` + `L5-T06`; list by tag returns one card.

---

## Task 2 — Write-back PATCH (Approach A)

**Contract:** `patch_note_section(...)` → 409 on mtime conflict.  
**Rules:** fence-aware body replace; sanitize; `atomic_write_text`; `bump_notes()`.  
**Required test:** section containing ````python` with a literal `## fake heading` must not truncate; next real `## \`MT1-T03\`` preserved.

---

## Task 3 — Tag list / add / rename / merge

**Contracts:** `list_tags` / `add_tag` / `rename_tag` / `merge_tags` (reject both note_topics).  
**`refs_updated`:** count includes **on-disk JSON files rewritten**. Assert after merge that `pack.json` no longer contains `oldfree` in `tags`.  
Then `bump_questions()`.

---

## Task 4 — Question CRUD + open fill + import

**Paths:** upsert into existing pack by `id`, else `data/questions/{kind}/_user/{safe_topic_id}.json`.  
**Import:** always via `upsert_question` — re-import same markdown → still **one** question.  
**Schema:** `McqQuestion` / `CodingMcqQuestion`; `CONTENT_KINDS` includes both.

---

## Task 5 — Loop session gate → quiz → FSRS

**Persistence:** SQLAlchemy `StudyLoopSession` in SQLite next to `ReviewCard` (columns: `session_id`, `user_id`, `tag`, `read_completed`, `read_card_ids` JSON, `practice_quiz_session_id`, timestamps). **Do not** use `data/behavior/study_loop_sessions.json`.

**CRITICAL contract — `resolve_practice_route`:**

```python
@dataclass
class PracticeRoute:
    domain: str  # vocab | math | study | code | mixed
    config: dict
    reason: str = ""

# Branch table:
# vocab.group.N     → vocab  {group_number, count}
# math-only (+gens) → math   {note_topic_id, count}
# coding-only       → code   {items, auto_generate=False}
# mcq/coding_mcq    → study  {items, auto_generate=False}
# mixed kinds       → mixed  {items, auto_generate=False}
# empty             → ValueError("no_practice_content")  # NEVER silent mathgen for L*
```

**Gate:** `read_completed = (len(list_read_cards(tag)) == 0)`.  
**start_practice:** require read → resolve route → `handler.start_session(domain=route.domain, config=route.config)`.

**Required tests:**

- `L5-T05` + mcq items → `domain == "study"` (not math).
- Empty `L5-T05` → `no_practice_content` (not math).
- Gate `read_required` until mark-read; vocab-only auto-completes.

**Routes:** `POST /study-loop/sessions`, `.../mark-read`, `.../start-practice`, `GET .../{id}`.

---

## Task 6 — Vocab tag stitch

Emit `vocab.group.N` + word `tags[]`. Practice path already covered by Task 5 vocab branch.

---

## Task 7 — Frontend Loop tab

TagPicker → session → ReadCardPanel → mark-read → practice via `GlobalQuizRunner`.  
**card_id:** use `::` ids from API; path calls must `encodeURIComponent(cardId)`.  
**409 on PATCH:** toast “Note changed on disk”; keep textarea draft; buttons **Reload latest** (re-GET, replace draft) vs **Overwrite anyway** (PATCH without / with force omitting stale mtime per API). Never silent discard.  
**Optional:** sort tags by `(due_count || 0) * (pillar_weight || 1)` — static multipliers only (not DKT).  
Client helpers under `/api/quiz/study-loop/*` as in full plan. Tab `"loop"` / `?tab=loop`.

---

## Task 8 — `POST /code/run` + IDE Run tests

Body `{ code, item? | item_id? }` → `grade_submission` outcomes. Mount missing route on `router.py`.

---

## Task 9 — Verification

```bash
python -m pytest tests/test_study_loop_read_cards.py tests/test_study_loop_tags.py tests/test_study_loop_questions.py tests/test_study_loop_session.py tests/test_quiz_code_run_api.py tests/test_quiz_content_bank_api.py tests/test_note_topics.py -q
npm run build
```

Update `docs/SESSION_LOG.md` when green.

---

## Acceptance criteria (epic)

1. `L5-T05` read card matches note; save updates note (mtime/409); fence fixture green.  
2. `MT1-T02` digest + bank/generator questions.  
3. Practice blocked until mark-read when a read card exists; vocab-only skips gate.  
4. **`L5-T05` practice with mcq packs uses `study`/`mixed`, never silent mathgen.** Empty tag → clear error.  
5. Free-tag rename/merge rewrites JSON on disk; note↔note merge → 400.  
6. Import MCQ / coding / coding_mcq / open math; idempotent; `_user` path.  
7. Coding: Run tests via `/api/quiz/code/run`.  
8. Practice upserts ReviewCards — **no second SRS**.  
9. `vocab.group.1` starts vocab quiz.  
10. pytest + `npm run build` green; no Study Flow RAG; no `/api/home/summary`.

---

## Suggested execution order

TDD: **1 → 2 → 3 → 4 → 5 → 6 → 7 → 8 → 9**.  
Do not lock Task 7 onto hardcoded math before Task 5’s `resolve_practice_route` is green.

---

*If Claude needs longer code samples, open the in-repo plan — do not invent a second architecture.*
