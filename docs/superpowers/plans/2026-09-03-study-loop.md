# Study Loop / Daily Learn Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship Study Loop on `/review` (Daily Learn): digest editable read cards from notes (Approach A write-back), stitch tags across lecture/math/vocab/questions, force read→practice, CRUD/import questions, Python IDE grading via `/api/quiz/code/run`, all on one `/api/quiz` + ReviewCard FSRS engine.

**Architecture:** Notes under `data/notes/` stay canonical. `backend/quiz/read_cards.py` digests `L*`/`MT*` sections via `parse_note_topics`. Tags index unions notes + `content_bank` + vocab. Study Loop session gates practice until mark-read. Practice always calls `handler.start_session`. Question CRUD mutates `data/questions/**` JSON validated by `content_schemas`. Frontend evolves `ReviewHubPage` Loop tab; reuse `GlobalQuizRunner` + `PythonCodeBlock`.

**Tech Stack:** FastAPI, Pydantic content schemas, SQLAlchemy ReviewCard FSRS, React + existing quiz client, Pyodide (`PythonCodeBlock`) + subprocess `code_runner`, pytest, Vite build.

## Global Constraints

- Approach **A**: read-card edits write back into note markdown (single source of truth).
- One quiz engine `/api/quiz` and one ReviewCard FSRS — no second SRS (ADR-001).
- Do not resurrect Study Flow / corpus RAG.
- Do not add `/api/home/summary`.
- Wire, don’t migrate; minimal diffs; match existing patterns.
- TDD for every new backend API.
- Python-only IDE for coding kinds in this epic.
- Commits only when the user asks (still include commit steps in this plan for when execution is authorized).
- Spec: `docs/superpowers/specs/2026-09-03-study-loop-design.md`.

### Pre-implementation locks (review 2026-09-03 — settle before Task 5)

1. **Domain routing is content-inspected**, never `else → domain=math`. See Task 5 `resolve_practice_route`.
2. **`rename_tag` / `merge_tags` rewrite on-disk JSON** under `data/questions/**/*.json` (`topic.note_topic_ids` + item `tags`) as part of `refs_updated`. Index-only updates are a lock violation.
3. **Heading-boundary scan is fence-aware** (ignore `##` inside fenced code). Required fixture before Task 2 done.
4. **Atomic writes:** every note/question write uses temp file + `os.replace()`. Optional env `STUDY_LOOP_GIT_CHECKPOINT=1` may auto-commit before write-back (default off — do not block PATCH on dirty tree).
5. **One invalidation point:** `backend/quiz/source_stamp.py` (`notes_stamp` / `questions_stamp` from mtimes). Readers (`read_cards`, `tag_index`, `content_bank`) check stamps; writers bump after replace. No ad-hoc “remember to bust N caches.”
6. **Imports are idempotent:** `import_questions` routes through `upsert_question` keyed by question `id` (no blind append duplicates).
7. **CRUD file layout:** `data/questions/{kind}/_user/{safe_topic_id}.json` — upsert by question `id` into the pack that already owns it, else into `_user` pack. Never scatter one-off files next to authored packs without `_user`.
8. **ADR math lanes vs hybrid steps:** ADR-001’s three lanes = product surfaces (SymPy generators · curated bank · OCR/whiteboard tutor). The **5-step order inside `domain=math`** is only the curated+generator resolution chain; OCR/whiteboard is a separate future entry into the same engine, not step 6 of that chain. Do not implement OCR in Study Loop Tasks 1–9.

### Pre-implementation locks (review pass 2 — 2026-09-03)

9. **`card_id` separator is `::`**, not `#` (URL fragment). Format: `{posix_note_path}::{topic_id}` e.g. `L05_pandas_operations_notes.md::L5-T05`. Paths always `.as_posix()`. Clients may still `encodeURIComponent` the whole id for path segments; FastAPI `{card_id:path}` must accept it. Legacy `#` parse is tolerated in `parse_card_id` only.
10. **Study Loop sessions live in SQLite** (SQLAlchemy model next to `ReviewCard`) — **not** `SQLAlchemy StudyLoopSession (SQLite next to ReviewCard)`. Wire don’t migrate: reuse the trusted persistence layer; no second flat-file session store.
11. **409 write-back UX (Task 7):** toast + keep draft in textarea; actions **Reload latest** vs **Overwrite anyway** (omit `expected_mtime` / force flag). Never silently discard the user’s edit.
12. **Read-card digester graceful degradation:** one bad note/topic must not 500 the whole list — skip + log; keep serving other cards.
13. **Answers are unit-free** for SymPy/`expression` grading — units belong in the problem text or a display-only `unit` field (`docs/QUESTION_CONTENT_FORMAT.md`).
14. **Optional later (not blocking Tasks 1–9):** trivial-param guard in `math_generators`; FSRS weight re-opt after ~1000 reviews; light difficulty-aware sampling in `start_session`.

---

## File structure map

| Path | Responsibility |
|------|----------------|
| `backend/quiz/read_cards.py` | Digest note sections → ReadCard views; get by card_id; list by tag. |
| `backend/quiz/note_writeback.py` | Fence-aware section patch; atomic write; Topic Index sync; mtime check. |
| `backend/quiz/source_stamp.py` | Shared notes/questions mtime stamps for cache coherence. |
| `backend/quiz/atomic_io.py` | `atomic_write_text(path, text)` via temp + `os.replace`. |
| `backend/quiz/tag_index.py` | List/add/rename/merge; **rewrites question JSON files** on rename/merge. |
| `backend/quiz/question_crud.py` | CRUD/import under `{kind}/_user/`; upsert-by-id. |
| `backend/quiz/study_loop.py` | Gate + `resolve_practice_route` + start-practice. |
| `backend/quiz/content_schemas.py` | Add `mcq` + `coding_mcq` kinds; keep SCHEMA_VERSION=1 with kind union. |
| `backend/quiz/content_bank.py` | Load new kinds; respect `source_stamp` for refresh. |
| `backend/quiz/router.py` | Mount study-loop + `/code/run` routes. |
| `backend/quiz/code_runner.py` | Already grades; expose run helper used by route. |
| `tests/test_study_loop_read_cards.py` | Digest + write-back + **fence-aware** fixture. |
| `tests/test_study_loop_tags.py` | Tag list/rename/merge **asserts JSON on disk rewritten**. |
| `tests/test_study_loop_questions.py` | CRUD + import **idempotent** + `_user` path. |
| `tests/test_study_loop_session.py` | Read gate + **domain resolution** (L* ≠ math). |
| `tests/test_quiz_code_run_api.py` | `/code/run` route. |
| `src/api/globalQuizClient.ts` | Client helpers. |
| `src/features/quiz/studyLoop/*` | TagPicker, ReadCardPanel, QuestionEditor, LoopTab. |
| `src/pages/quiz/ReviewHubPage.tsx` | Add Loop tab; wire runner. |
| `src/components/dashboard/StudyLoopWidget.tsx` | CTA → `?tab=loop`. |
| `docs/QUESTION_CONTENT_FORMAT.md` | Document mcq + coding_mcq + `_user` packs. |
| `docs/SESSION_LOG.md` | Session note when verified. |

---

### Task 1: Note section digester + read-card API

**Files:**
- Create: `backend/quiz/read_cards.py`
- Modify: `backend/quiz/router.py`
- Test: `tests/test_study_loop_read_cards.py`

**Interfaces:**
- Consumes: `backend.transcripts.note_topics.parse_note_topics`, `canonicalize_topic_id`, `backend.paths.NOTES_DIR`, `backend.transcripts.library.is_indexable_library_note` (or equivalent path filter)
- Produces:
  - `ReadCard` dataclass / dict with keys `card_id`, `tag`, `title`, `body_markdown`, `heading_markdown`, `note_path`, `mtime`, `source`, `char_count`
  - `def make_card_id(note_path: str, topic_id: str) -> str`
  - `def list_read_cards(*, tag: str | None = None, root: Path | None = None) -> list[dict]`
  - `def get_read_card(card_id: str, *, root: Path | None = None) -> dict | None`
  - Routes: `GET /api/quiz/study-loop/read-cards`, `GET /api/quiz/study-loop/read-cards/{card_id:path}`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_study_loop_read_cards.py
from pathlib import Path

from backend.quiz import read_cards as rc


def test_digest_l5_topic_from_fixture(tmp_path: Path):
    note = tmp_path / "L05_pandas_operations_notes.md"
    note.write_text(
        "# Pandas\n\n## Topic Index\n\n| ID | Topic |\n|---|---|\n| `L5-T05` | Unique values |\n\n"
        "## `L5-T05` — Unique values\n\n"
        "Use `unique()` and `nunique()`.\n\n"
        "## `L5-T06` — Mutability\n\n"
        "Assigning through iloc.\n",
        encoding="utf-8",
    )
    cards = rc.list_read_cards(tag="L5-T05", root=tmp_path)
    assert len(cards) == 1
    card = cards[0]
    assert card["card_id"] == "L05_pandas_operations_notes.md::L5-T05"
    assert card["tag"] == "L5-T05"
    assert "unique()" in card["body_markdown"]
    assert "Mutability" not in card["body_markdown"]
    got = rc.get_read_card(card["card_id"], root=tmp_path)
    assert got is not None
    assert got["title"].lower().startswith("unique")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_study_loop_read_cards.py::test_digest_l5_topic_from_fixture -v`

Expected: FAIL with `ModuleNotFoundError` or `ImportError` for `backend.quiz.read_cards`

- [ ] **Step 3: Write minimal implementation**

```python
# backend/quiz/read_cards.py
from __future__ import annotations

from pathlib import Path
from typing import Any

from backend import paths
from backend.transcripts.note_topics import canonicalize_topic_id, parse_note_topics


def make_card_id(note_path: str, topic_id: str) -> str:
    rel = Path(str(note_path).replace("\\", "/")).as_posix().lstrip("/")
    tid = canonicalize_topic_id(topic_id) or topic_id.strip().upper()
    return f"{rel}::{tid}"


def parse_card_id(card_id: str) -> tuple[str, str]:
    raw = Path(str(card_id or "").replace("\\", "/")).as_posix()
    if "::" in raw:
        path, tag = raw.rsplit("::", 1)
    elif "#" in raw:
        path, tag = raw.rsplit("#", 1)
    else:
        raise ValueError("card_id must look like path::TOPIC")
    tid = canonicalize_topic_id(tag) or tag.strip().upper()
    return path, tid


def _iter_note_files(root: Path) -> list[Path]:
    if not root.is_dir():
        return []
    out: list[Path] = []
    for p in sorted(root.rglob("*.md")):
        if not p.is_file():
            continue
        rel = p.relative_to(root).as_posix()
        if rel.startswith("rules/") or "/rules/" in f"/{rel}":
            continue
        out.append(p)
    return out


def list_read_cards(*, tag: str | None = None, root: Path | None = None) -> list[dict[str, Any]]:
    base = Path(root) if root else paths.NOTES_DIR
    want = None
    if tag:
        want = (canonicalize_topic_id(tag) or tag.strip().upper())
    cards: list[dict[str, Any]] = []
    for path in _iter_note_files(base):
        rel = path.relative_to(base).as_posix()
        text = path.read_text(encoding="utf-8")
        mtime = path.stat().st_mtime
        for topic in parse_note_topics(text, min_body_chars=1, max_topics=80):
            tid = canonicalize_topic_id(topic.topic_id) or topic.topic_id
            if want and tid.upper() != want.upper():
                continue
            # Recover heading line for write-back later
            heading = ""
            for line in text.splitlines():
                if tid.upper() in line.upper() and line.lstrip().startswith("#"):
                    heading = line
                    break
            cards.append(
                {
                    "card_id": make_card_id(rel, tid),
                    "tag": tid,
                    "title": topic.title,
                    "body_markdown": topic.body,
                    "heading_markdown": heading,
                    "note_path": rel,
                    "mtime": mtime,
                    "source": topic.source,
                    "char_count": len(topic.body),
                }
            )
    return cards


def get_read_card(card_id: str, *, root: Path | None = None) -> dict[str, Any] | None:
    path, tid = parse_card_id(card_id)
    for card in list_read_cards(tag=tid, root=root):
        if card["note_path"] == path.replace("\\", "/") and card["tag"].upper() == tid.upper():
            return card
    return None
```

Wire routes in `backend/quiz/router.py` (before `/{session_id}/…` catch-alls — place with other `/content` static paths):

```python
@router.get("/study-loop/read-cards")
def get_study_loop_read_cards(
    tag: str | None = None,
    user: User = Depends(get_current_user),
):
    from backend.quiz import read_cards as rc

    _ = user
    items = rc.list_read_cards(tag=tag)
    return {"items": items, "count": len(items)}


@router.get("/study-loop/read-cards/{card_id:path}")
def get_study_loop_read_card(
    card_id: str,
    user: User = Depends(get_current_user),
):
    from backend.quiz import read_cards as rc

    _ = user
    # FastAPI may decode; accept path::tag
    card = rc.get_read_card(card_id)
    if card is None:
        raise HTTPException(status_code=404, detail="Read card not found.")
    return card
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_study_loop_read_cards.py::test_digest_l5_topic_from_fixture -v`

Expected: PASS

Also add a smoke test against real notes when present:

```python
def test_real_notes_have_l5_or_mt1():
    from backend.paths import NOTES_DIR
    from backend.quiz import read_cards as rc

    if not (NOTES_DIR / "L05_pandas_operations_notes.md").is_file():
        return
    cards = rc.list_read_cards(tag="L5-T05")
    assert cards and "unique" in cards[0]["body_markdown"].lower()
```

- [ ] **Step 5: Commit** (only if user authorized commits)

```bash
git add backend/quiz/read_cards.py backend/quiz/router.py tests/test_study_loop_read_cards.py
git commit -m "$(cat <<'EOF'
feat(quiz): digest note sections into study-loop read cards

EOF
)"
```

---

### Task 2: Write-back PATCH for section body (Approach A)

**Files:**
- Create: `backend/quiz/note_writeback.py`
- Create: `backend/quiz/atomic_io.py` (if not already from shared helper)
- Create / use: `backend/quiz/source_stamp.py`
- Modify: `backend/quiz/router.py`
- Modify: `tests/test_study_loop_read_cards.py`

**Interfaces:**
- Consumes: `read_cards.parse_card_id`, `atomic_write_text`, `source_stamp.bump_notes`
- Produces:
  - `def patch_note_section(*, note_path: str, topic_id: str, body_markdown: str, title: str | None, expected_mtime: float | None, root: Path | None, user_id: int | None, db: Session | None) -> dict`
  - Raises `FileNotFoundError`, `ValueError` (mtime conflict → router maps to 409)
  - Route: `PATCH /api/quiz/study-loop/read-cards/{card_id:path}`
  - **Fence-aware boundary:** while scanning for next `#{2,4}` heading, track `in_fence`; lines inside \`\`\` fences never count as section boundaries even if they contain `##`.
  - **Atomic write:** sanitize → write temp beside target → `os.replace` → `bump_notes()`.

- [ ] **Step 1: Write the failing test**

```python
def test_writeback_replaces_section_body_only(tmp_path: Path):
    from backend.quiz import note_writeback as wb
    from backend.quiz import read_cards as rc

    note = tmp_path / "math" / "MT1_aptitude_interview_notes.md"
    note.parent.mkdir(parents=True)
    note.write_text(
        "# MT1\n\n## Topic Index\n\n- `MT1-T02` — LCM & HCF\n\n"
        "## `MT1-T02` — LCM & HCF\n\nOld body.\n\n"
        "## `MT1-T03` — Percentages\n\nKeep me.\n",
        encoding="utf-8",
    )
    mtime = note.stat().st_mtime
    out = wb.patch_note_section(
        note_path="math/MT1_aptitude_interview_notes.md",
        topic_id="MT1-T02",
        body_markdown="New body with formula.",
        title="LCM and HCF",
        expected_mtime=mtime,
        root=tmp_path,
    )
    text = note.read_text(encoding="utf-8")
    assert "New body with formula." in text
    assert "Keep me." in text
    assert "Old body." not in text
    assert "LCM and HCF" in text
    card = rc.get_read_card(out["card_id"], root=tmp_path)
    assert card and "New body" in card["body_markdown"]


def test_writeback_ignores_hash_heading_inside_code_fence(tmp_path: Path):
    """False ## inside a fence must not truncate the section."""
    from backend.quiz import note_writeback as wb

    note = tmp_path / "math" / "MT1_fence.md"
    note.parent.mkdir(parents=True)
    note.write_text(
        "# MT1\n\n"
        "## `MT1-T02` — LCM\n\n"
        "Intro.\n\n"
        "```python\n"
        "# comment\n"
        "## fake heading inside fence\n"
        "print(1)\n"
        "```\n\n"
        "Still in section.\n\n"
        "## `MT1-T03` — Next\n\n"
        "Keep me.\n",
        encoding="utf-8",
    )
    wb.patch_note_section(
        note_path="math/MT1_fence.md",
        topic_id="MT1-T02",
        body_markdown=(
            "Replaced.\n\n```python\n## fake heading inside fence\nprint(2)\n```\n\nTail.\n"
        ),
        expected_mtime=note.stat().st_mtime,
        root=tmp_path,
    )
    text = note.read_text(encoding="utf-8")
    assert "Replaced." in text
    assert "Keep me." in text
    assert "## `MT1-T03`" in text
    assert text.index("Replaced.") < text.index("## `MT1-T03`")
    assert "## fake heading inside fence" in text
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_study_loop_read_cards.py::test_writeback_replaces_section_body_only tests/test_study_loop_read_cards.py::test_writeback_ignores_hash_heading_inside_code_fence -v`

Expected: FAIL importing `note_writeback`

- [ ] **Step 3: Write minimal implementation**

```python
# backend/quiz/note_writeback.py
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from backend import paths
from backend.transcripts.note_lint import sanitize_note_content
from backend.transcripts.note_topics import canonicalize_topic_id
from backend.quiz.read_cards import make_card_id


_HEADING_RE = re.compile(r"^(#{2,4})\s+(.*)$")


def patch_note_section(
    *,
    note_path: str,
    topic_id: str,
    body_markdown: str,
    title: str | None = None,
    expected_mtime: float | None = None,
    root: Path | None = None,
) -> dict[str, Any]:
    base = Path(root) if root else paths.NOTES_DIR
    rel = note_path.replace("\\", "/").lstrip("/")
    path = (base / rel).resolve()
    if not path.is_relative_to(base.resolve()):
        raise ValueError("Invalid note path.")
    if not path.is_file():
        raise FileNotFoundError(rel)
    current_mtime = path.stat().st_mtime
    if expected_mtime is not None and abs(current_mtime - float(expected_mtime)) > 0.001:
        raise ValueError("mtime_conflict")
    tid = canonicalize_topic_id(topic_id) or topic_id.strip().upper()
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines(keepends=True)
    start = end = None
    start_level = 2
    for i, line in enumerate(lines):
        m = _HEADING_RE.match(line.rstrip("\n"))
        if not m:
            continue
        level = len(m.group(1))
        heading = m.group(2)
        if tid.lower() in heading.lower().replace("`", ""):
            start = i
            start_level = level
            continue
        if start is not None and level <= start_level:
            end = i
            break
    if start is None:
        raise FileNotFoundError(f"section {tid}")
    if end is None:
        end = len(lines)
    heading_line = lines[start].rstrip("\n")
    hm = _HEADING_RE.match(heading_line)
    marks = hm.group(1) if hm else "##"
    new_title = (title or "").strip()
    if new_title:
        heading_line = f"{marks} `{tid}` — {new_title}"
    else:
        heading_line = lines[start].rstrip("\n")
    body = body_markdown.strip("\n")
    new_block = heading_line + "\n\n" + body + ("\n" if body else "")
    # Ensure separation before next heading
    if end < len(lines) and not new_block.endswith("\n"):
        new_block += "\n"
    if end < len(lines) and not lines[end].startswith("\n") and not new_block.endswith("\n\n"):
        new_block += "\n"
    updated = "".join(lines[:start]) + new_block + "".join(lines[end:])
    # Topic Index bullet/table title sync
    if new_title:
        updated = re.sub(
            rf"(\|\s*`?{re.escape(tid)}`?\s*\|\s*)([^|]+)\|",
            rf"\1{new_title} |",
            updated,
            count=1,
            flags=re.IGNORECASE,
        )
        updated = re.sub(
            rf"([-*]\s*`?{re.escape(tid)}`?\s*(?:—|-|–|:)\s*)(.+)$",
            rf"\1{new_title}",
            updated,
            count=1,
            flags=re.IGNORECASE | re.MULTILINE,
        )
    updated = sanitize_note_content(updated)
    path.write_text(updated, encoding="utf-8")
    return {
        "card_id": make_card_id(rel, tid),
        "note_path": rel,
        "tag": tid,
        "mtime": path.stat().st_mtime,
        "title": new_title or None,
    }
```

Router:

```python
class ReadCardPatchBody(BaseModel):
    body_markdown: str
    title: str | None = None
    expected_mtime: float | None = None


@router.patch("/study-loop/read-cards/{card_id:path}")
def patch_study_loop_read_card(
    card_id: str,
    body: ReadCardPatchBody,
    user: User = Depends(get_current_user),
):
    from backend.quiz import note_writeback as wb
    from backend.quiz.read_cards import parse_card_id

    _ = user
    try:
        note_path, topic_id = parse_card_id(card_id)
        result = wb.patch_note_section(
            note_path=note_path,
            topic_id=topic_id,
            body_markdown=body.body_markdown,
            title=body.title,
            expected_mtime=body.expected_mtime,
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        if str(exc) == "mtime_conflict":
            raise HTTPException(status_code=409, detail="Note changed on disk. Reload before saving.") from exc
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return result
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_study_loop_read_cards.py -v`

Expected: PASS

- [ ] **Step 5: Commit** (if authorized)

```bash
git add backend/quiz/note_writeback.py backend/quiz/router.py tests/test_study_loop_read_cards.py
git commit -m "$(cat <<'EOF'
feat(quiz): write read-card edits back into note files

EOF
)"
```

---

### Task 3: Tag list / add / rename / merge API

**Files:**
- Create: `backend/quiz/tag_index.py`
- Modify: `backend/quiz/router.py`
- Test: `tests/test_study_loop_tags.py`

**Interfaces:**
- Consumes: `read_cards.list_read_cards`, `content_bank.load_catalog`, vocab `load_words`
- Produces:
  - `def list_tags(*, q: str | None = None, kind: str | None = None) -> list[dict]`
  - `def add_tag(tag_id: str, *, question_id: str | None = None, word_ids: list[int] | None = None, note_path: str | None = None, topic_id: str | None = None) -> dict`
  - `def rename_tag(old: str, new: str) -> dict` — free tags + vocab tags + question tags; note-topic rename rewrites headings via writeback helper for each matching card; **must rewrite every `data/questions/**/*.json`** that lists `old` in `topic.note_topic_ids` or item `tags` (atomic write + `bump_questions`). `refs_updated` counts disk files + vocab rows + notes touched — not index-only.
  - `def merge_tags(from_tag: str, into_tag: str) -> dict` — reject if both are `note_topic`; same **on-disk JSON rewrite** as rename
  - Routes: `GET/POST /study-loop/tags`, `PATCH /study-loop/tags/{tag}`, `POST /study-loop/tags/merge`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_study_loop_tags.py
import json
from pathlib import Path

from backend.quiz import tag_index as ti


def test_list_tags_includes_note_and_question(tmp_path: Path, monkeypatch):
    notes = tmp_path / "notes"
    notes.mkdir()
    (notes / "L05.md").write_text(
        "## `L5-T05` — Unique\n\nBody here is long enough.\n",
        encoding="utf-8",
    )
    qdir = tmp_path / "questions" / "math" / "x"
    qdir.mkdir(parents=True)
    (qdir / "pack.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "kind": "math",
                "topic": {
                    "topic_id": "math.demo.unique",
                    "title": "Unique",
                    "note_topic_ids": ["L5-T05"],
                    "path": [],
                },
                "questions": [
                    {
                        "id": "math.demo.unique.q001",
                        "problem": "1+1",
                        "answer": "2",
                        "tags": ["warmup"],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(ti, "NOTES_DIR", notes)
    monkeypatch.setattr(ti, "QUESTIONS_DIR", tmp_path / "questions")
    tags = {t["id"]: t for t in ti.list_tags()}
    assert "L5-T05" in tags
    assert tags["L5-T05"]["has_read_card"] is True
    assert tags["L5-T05"]["question_count"] >= 1
    assert "warmup" in tags


def test_merge_free_into_note_topic(tmp_path: Path, monkeypatch):
    qdir = tmp_path / "questions" / "math" / "x"
    qdir.mkdir(parents=True)
    path = qdir / "pack.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "kind": "math",
                "topic": {
                    "topic_id": "math.demo.merge",
                    "title": "Merge",
                    "note_topic_ids": ["L5-T05"],
                    "path": [],
                },
                "questions": [
                    {
                        "id": "math.demo.merge.q001",
                        "problem": "x",
                        "answer": "1",
                        "tags": ["oldfree"],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(ti, "QUESTIONS_DIR", tmp_path / "questions")
    monkeypatch.setattr(ti, "NOTES_DIR", tmp_path / "notes")
    (tmp_path / "notes").mkdir()
    result = ti.merge_tags("oldfree", "L5-T05")
    # CRITICAL: source JSON must change on disk (Approach A / wire-don't-migrate)
    disk = json.loads(path.read_text(encoding="utf-8"))
    assert "oldfree" not in disk["questions"][0]["tags"]
    assert "L5-T05" in disk["questions"][0]["tags"]
    assert result["refs_updated"] >= 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_study_loop_tags.py -v`

Expected: FAIL missing module

- [ ] **Step 3: Write minimal implementation**

Implement `tag_index.py` that:

1. Scans notes via `list_read_cards()` for `note_topic` tags.
2. Loads catalog (injectable root) and collects `note_topic_ids` + item `tags`.
3. Loads vocab words; emits `vocab.group.{n}` and each free tag.
4. `merge_tags`: if both match `^(L|MT)\d+-T\d+$` → `ValueError("cannot_merge_note_topics")`.
5. **Rewrite every matching `data/questions/**/*.json` in place** (topic.note_topic_ids + question.tags) via `atomic_write_text`; update curriculum.json; then `bump_questions()` / `load_catalog(refresh=True)`.
6. `rename_tag` for note topics: for each read card with that tag, rewrite heading id via regex on full file + curriculum.json `note_topic_id` fields + same JSON rewrite as merge.

Expose router endpoints with Pydantic bodies:

```python
class TagCreateBody(BaseModel):
    id: str
    question_id: str | None = None
    word_ids: list[int] | None = None
    note_path: str | None = None
    topic_id: str | None = None


class TagRenameBody(BaseModel):
    new_id: str
    label: str | None = None


class TagMergeBody(BaseModel):
    from_tag: str
    into_tag: str
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_study_loop_tags.py -v`

Expected: PASS

- [ ] **Step 5: Commit** (if authorized)

```bash
git add backend/quiz/tag_index.py backend/quiz/router.py tests/test_study_loop_tags.py
git commit -m "$(cat <<'EOF'
feat(quiz): study-loop tag index with rename and merge

EOF
)"
```

---

### Task 4: Question CRUD + open-answer fill + import parsers

**Files:**
- Create: `backend/quiz/question_crud.py`
- Modify: `backend/quiz/content_schemas.py` — add `McqQuestion`, `CodingMcqQuestion`; extend `ContentFile.kind` and `CONTENT_KINDS`
- Modify: `backend/quiz/content_bank.py` — load/build items for `mcq` / `coding_mcq`
- Modify: `docs/QUESTION_CONTENT_FORMAT.md`
- Modify: `backend/quiz/router.py`
- Test: `tests/test_study_loop_questions.py`

**Interfaces:**
- Consumes: `ContentFile`, `load_catalog`, `QUESTIONS_DIR`, `atomic_write_text`, `source_stamp.bump_questions`
- Produces:
  - `def list_questions(*, tag: str | None, kind: str | None) -> list[dict]`
  - `def upsert_question(payload: dict) -> dict` — if `id` exists in any pack, update that file in place; else write/merge into `data/questions/{kind}/_user/{safe_topic_id}.json` (one ContentFile per topic_id under `_user`)
  - `def patch_question(question_id: str, fields: dict) -> dict`
  - `def delete_question(question_id: str) -> dict`
  - `def import_questions(raw: dict | list | str, *, kind: str, topic_id: str, note_topic_ids: list[str]) -> dict` — **idempotent:** each question goes through `upsert_question` by `id`; re-import same file → `imported` may be 0, `updated` ≥ 1, ** count unchanged
  - Routes under `/study-loop/questions*`

**File naming (locked):**

```text
data/questions/{kind}/_user/{safe_topic_id}.json
# safe_topic_id = topic_id with unsafe path chars → "_"
# Hand-authored packs stay under data/questions/{kind}/<authored>/…
# CRUD never creates sibling one-offs outside _user unless updating an existing authored file by id
```

- [ ] **Step 1: Write the failing test**

```python
# tests/test_study_loop_questions.py
from pathlib import Path

from backend.quiz import question_crud as qc


def test_create_and_patch_open_math(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(qc, "QUESTIONS_DIR", tmp_path)
    created = qc.upsert_question(
        {
            "kind": "math",
            "topic_id": "math.loop.demo",
            "topic_title": "Demo",
            "note_topic_ids": ["MT1-T02"],
            "question": {
                "id": "math.loop.demo.q001",
                "problem": "Prove something",
                "answer": "",
                "answer_format": "open",
                "tags": ["no-answer"],
            },
        }
    )
    assert created["id"] == "math.loop.demo.q001"
    patched = qc.patch_question(
        "math.loop.demo.q001",
        {"answer": "42", "answer_format": "number", "solution_steps": ["step"], "tags": []},
    )
    assert patched["answer"] == "42"
    assert patched["answer_format"] == "number"
    items = qc.list_questions(tag="MT1-T02", kind="math")
    assert any(i["id"] == "math.loop.demo.q001" for i in items)


def test_import_mcq_markdown(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(qc, "QUESTIONS_DIR", tmp_path)
    md = """
Q. What is HCF of 8 and 12?
- 2
- *4
- 8
- 24
"""
    result = qc.import_questions(
        md,
        kind="mcq",
        topic_id="mcq.loop.hcf",
        note_topic_ids=["MT1-T02"],
    )
    assert result["imported"] == 1
    items = qc.list_questions(tag="MT1-T02", kind="mcq")
    assert items[0]["answer_index"] == 1
    # Idempotent: second import must not duplicate
    again = qc.import_questions(
        md,
        kind="mcq",
        topic_id="mcq.loop.hcf",
        note_topic_ids=["MT1-T02"],
    )
    assert again["imported"] + again.get("updated", 0) >= 1
    assert len(qc.list_questions(tag="MT1-T02", kind="mcq")) == 1
    user_pack = tmp_path / "mcq" / "_user" / "mcq.loop.hcf.json"
    assert user_pack.is_file()
```

Schema additions (exact):

```python
# in content_schemas.py
class McqQuestion(BaseModel):
    model_config = ConfigDict(extra="allow")
    id: str = Field(..., min_length=1, max_length=160)
    question: str = Field(..., min_length=1)
    options: list[str] = Field(..., min_length=2)
    answer_index: int = Field(..., ge=0)
    difficulty: Difficulty = "medium"
    explanation: str = ""
    hint: str = ""
    tags: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _idx(self) -> McqQuestion:
        if self.answer_index >= len(self.options):
            raise ValueError("answer_index out of range")
        return self


class CodingMcqQuestion(BaseModel):
    model_config = ConfigDict(extra="allow")
    id: str = Field(..., min_length=1, max_length=160)
    prompt: str = Field(..., min_length=1)
    options: list[str] = Field(..., min_length=2)
    answer_index: int = Field(..., ge=0)
    starter_code: str = ""
    difficulty: Difficulty = "medium"
    explanation: str = ""
    hint: str = ""
    tags: list[str] = Field(default_factory=list)
```

Update `ContentFile.kind` to `Literal["math", "coding", "mcq", "coding_mcq"]` and `CONTENT_KINDS = ("math", "coding", "mcq", "coding_mcq")`.

Normalize items in `content_bank`:

```python
def _mcq_item(topic: TopicEntry, q: Any) -> dict[str, Any]:
    return {
        "kind": "mcq",
        "id": q.id,
        "question": q.question,
        "options": list(q.options),
        "answer_index": q.answer_index,
        "difficulty": q.difficulty,
        "explanation": q.explanation,
        "hint": q.hint,
        "topic": topic.topic_id,
        "topic_id": topic.topic_id,
        "tags": list(q.tags),
        "note_topic_ids": list(topic.note_topic_ids),
        "content_kind": "mcq",
    }
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_study_loop_questions.py -v`

Expected: FAIL

- [ ] **Step 3: Implement CRUD + import + schema + bank loaders + routes**

`import_questions` for markdown MCQ: split on `^Q\.`, parse lines starting with `-`, treat `*` or `(*)` prefix as correct option.

`PATCH` must locate file by scanning catalog `source_file`, update the question dict, validate with schema, write JSON, `load_catalog(refresh=True)`.

- [ ] **Step 4: Run tests**

Run: `python -m pytest tests/test_study_loop_questions.py tests/test_quiz_content_bank_api.py -v`

Expected: PASS (catalog still loads; new kinds empty dirs ok)

- [ ] **Step 5: Commit** (if authorized)

```bash
git add backend/quiz/question_crud.py backend/quiz/content_schemas.py backend/quiz/content_bank.py backend/quiz/router.py docs/QUESTION_CONTENT_FORMAT.md tests/test_study_loop_questions.py
git commit -m "$(cat <<'EOF'
feat(quiz): study-loop question CRUD, open-answer fill, and imports

EOF
)"
```

---

### Task 5: Study Loop session orchestration (read gate → quiz → FSRS)

**Files:**
- Create: `backend/quiz/study_loop.py`
- Modify: `backend/quiz/router.py`
- Test: `tests/test_study_loop_session.py`

**Interfaces:**
- Consumes: `read_cards.list_read_cards`, `handler.start_session`, `content_bank` items-by-tag, math generators **only when route is math**
- Produces:
  - `def create_loop_session(*, user_id: int, tag: str) -> dict`
  - `def mark_read(*, user_id: int, session_id: str) -> dict`
  - `def resolve_practice_route(tag: str, *, count: int = 5, kinds: list[str] | None = None) -> PracticeRoute`
  - `def list_bank_items_for_tag(tag: str, *, kinds: list[str] | None = None) -> list[dict]`
  - `def math_generators_for_tag(tag: str) -> list` — thin wrapper; empty for non-MT / no recipes
  - `def start_practice(*, db, user, session_id: str, count: int = 5, kinds: list[str] | None = None) -> dict`
  - Persistence: SQLAlchemy `StudyLoopSession` (SQLite next to ReviewCard); tests use DB fixture — **not** a flat JSON file

**CRITICAL:** Never hardcode `else → domain=math`. Inspect bank content under the tag (fixes L5-T05 / lecture tags).

```python
from dataclasses import dataclass, field
from typing import Any
import re

_VOCAB_GROUP = re.compile(r"^vocab\.group\.(\d+)$", re.I)

@dataclass
class PracticeRoute:
    domain: str  # vocab | math | study | code | mixed
    config: dict[str, Any] = field(default_factory=dict)
    reason: str = ""

def resolve_practice_route(tag: str, *, count: int = 5, kinds: list[str] | None = None) -> PracticeRoute:
    tid = (tag or "").strip()
    m = _VOCAB_GROUP.match(tid)
    if m:
        return PracticeRoute("vocab", {"group_number": int(m.group(1)), "count": count}, "vocab_group")

    items = list_bank_items_for_tag(tid, kinds=kinds)
    buckets: dict[str, int] = {}
    for it in items:
        k = (it.get("content_kind") or it.get("kind") or "").lower()
        if k in ("mcq", "study"):
            b = "mcq"
        elif k == "coding_mcq":
            b = "coding_mcq"
        elif k in ("coding", "code"):
            b = "coding"
        elif k == "math":
            b = "math"
        else:
            b = "other"
        buckets[b] = buckets.get(b, 0) + 1

    has_math_gen = bool(math_generators_for_tag(tid))
    mathish = buckets.get("math", 0) > 0 or has_math_gen
    coding = buckets.get("coding", 0) > 0
    mcq = buckets.get("mcq", 0) + buckets.get("coding_mcq", 0) > 0

    if mathish and not coding and not mcq:
        return PracticeRoute("math", {"note_topic_id": tid, "count": count}, "math_only")
    if coding and not mathish and not mcq:
        return PracticeRoute("code", {"items": items[:count], "auto_generate": False}, "coding_only")
    if mcq and not mathish and not coding:
        return PracticeRoute("study", {"items": items[:count], "auto_generate": False}, "mcq_only")
    if mathish or coding or mcq:
        if not items and mathish:
            return PracticeRoute("math", {"note_topic_id": tid, "count": count}, "math_gen_fill")
        return PracticeRoute("mixed", {"items": items[:count], "auto_generate": False}, "mixed_kinds")
    raise ValueError("no_practice_content")
```

| Condition | domain | config |
|-----------|--------|--------|
| `vocab.group.N` | `vocab` | `group_number`, `count` |
| Only math bank and/or generators | `math` | `note_topic_id=tag` |
| Only coding | `code` | `items`, `auto_generate=False` |
| Only mcq / coding_mcq | `study` | `items`, `auto_generate=False` |
| Mix of kinds | `mixed` | `items`, `auto_generate=False` |
| Empty (e.g. bare `L5-T05`) | — | `ValueError("no_practice_content")` → HTTP 400/404; **never** silent mathgen |

Gate: `read_completed = (len(list_read_cards(tag)) == 0)`.

`start_practice`: require `read_completed` → `route = resolve_practice_route(...)` → `handler.start_session(..., domain=route.domain, config=route.config)` → store practice session id → return payload for `GlobalQuizRunner`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_study_loop_session.py
import pytest
from backend.quiz import study_loop as sl


def test_practice_blocked_until_mark_read(tmp_path, monkeypatch):
    monkeypatch.setattr(sl, "STORE_PATH", tmp_path / "sessions.json")
    monkeypatch.setattr(sl, "list_read_cards", lambda **kw: [{"card_id": "n.md::L5-T05", "tag": "L5-T05"}])
    sess = sl.create_loop_session(user_id=1, tag="L5-T05")
    assert sess["read_completed"] is False
    with pytest.raises(ValueError, match="read_required"):
        sl.start_practice(db=None, user=None, session_id=sess["session_id"])
    sl.mark_read(user_id=1, session_id=sess["session_id"])
    assert sl.get_session(1, sess["session_id"])["read_completed"] is True


def test_vocab_only_auto_completes_read(tmp_path, monkeypatch):
    monkeypatch.setattr(sl, "STORE_PATH", tmp_path / "sessions.json")
    monkeypatch.setattr(sl, "list_read_cards", lambda **kw: [])
    sess = sl.create_loop_session(user_id=1, tag="vocab.group.1")
    assert sess["read_completed"] is True


def test_resolve_l_tag_with_mcq_is_study_not_math(monkeypatch):
    monkeypatch.setattr(
        sl,
        "list_bank_items_for_tag",
        lambda tag, kinds=None: [{"id": "mcq.l5.q1", "kind": "mcq", "content_kind": "mcq"}],
    )
    monkeypatch.setattr(sl, "math_generators_for_tag", lambda tag: [])
    route = sl.resolve_practice_route("L5-T05")
    assert route.domain == "study"
    assert route.config.get("auto_generate") is False


def test_resolve_empty_l_tag_errors_not_math(monkeypatch):
    monkeypatch.setattr(sl, "list_bank_items_for_tag", lambda tag, kinds=None: [])
    monkeypatch.setattr(sl, "math_generators_for_tag", lambda tag: [])
    with pytest.raises(ValueError, match="no_practice_content"):
        sl.resolve_practice_route("L5-T05")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_study_loop_session.py -v`

Expected: FAIL

- [ ] **Step 3: Implement study_loop.py + routes**

Wire `POST /study-loop/sessions`, `.../mark-read`, `.../start-practice`, `GET .../{id}`. Map `no_practice_content` → HTTP 400/404. **Do not** lock Task 7 UI onto a hardcoded math domain.

- [ ] **Step 4: Run tests**

Run: `python -m pytest tests/test_study_loop_session.py -v`

Expected: PASS

- [ ] **Step 5: Commit** (if authorized)

```bash
git add backend/quiz/study_loop.py backend/quiz/router.py tests/test_study_loop_session.py
git commit -m "feat(quiz): study-loop session with content-inspected domain routing"
```

---

### Task 6: Vocab tag stitch into loop

**Files:**
- Modify: `backend/quiz/tag_index.py` (vocab group emission + attach)
- Modify: `backend/quiz/study_loop.py` (`start_practice` vocab branch — confirm)
- Modify: `backend/vocab` word update only if an existing PATCH path can add tags; else add thin helper in `tag_index.add_tag`
- Test: `tests/test_study_loop_tags.py` (extend)

**Interfaces:**
- Consumes: `backend.vocab.words.load_words`, save words helper already used by vocab routes
- Produces: tags `vocab.group.{n}` with `vocab_count`; `add_tag` with `word_ids` appends to each word’s `tags`

- [ ] **Step 1: Write the failing test**

```python
def test_vocab_group_tag_listed(monkeypatch):
    from backend.quiz import tag_index as ti

    monkeypatch.setattr(
        ti,
        "load_words",
        lambda db=None: [
            {"id": 1, "word": "abate", "group_number": 2, "tags": ["emotion"]},
            {"id": 2, "word": "chicanery", "group_number": 2, "tags": []},
        ],
    )
    monkeypatch.setattr(ti, "list_read_cards", lambda **kw: [])
    monkeypatch.setattr(ti, "iter_question_tags", lambda: [])
    tags = {t["id"]: t for t in ti.list_tags()}
    assert tags["vocab.group.2"]["vocab_count"] == 2
    assert tags["emotion"]["vocab_count"] == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_study_loop_tags.py::test_vocab_group_tag_listed -v`

Expected: FAIL until helpers exist

- [ ] **Step 3: Implement vocab emission + attach**

```python
def _vocab_tags(words: list[dict]) -> list[dict]:
    groups: dict[int, int] = {}
    free: dict[str, int] = {}
    for w in words:
        gn = int(w.get("group_number") or 0)
        if gn:
            groups[gn] = groups.get(gn, 0) + 1
        for t in w.get("tags") or []:
            key = str(t).strip().lower()
            if key:
                free[key] = free.get(key, 0) + 1
    out = []
    for gn, count in sorted(groups.items()):
        out.append(
            {
                "id": f"vocab.group.{gn}",
                "kind": "vocab_group",
                "label": f"GRE group {gn}",
                "vocab_count": count,
                "question_count": 0,
                "has_read_card": False,
                "note_paths": [],
            }
        )
    for tag, count in sorted(free.items()):
        out.append(
            {
                "id": tag,
                "kind": "free",
                "label": tag,
                "vocab_count": count,
                "question_count": 0,
                "has_read_card": False,
                "note_paths": [],
            }
        )
    return out
```

Ensure `start_practice` for `vocab.group.N` uses `domain="vocab"` (already specified in Task 5).

- [ ] **Step 4: Run tests**

Run: `python -m pytest tests/test_study_loop_tags.py tests/test_study_loop_session.py -v`

Expected: PASS

- [ ] **Step 5: Commit** (if authorized)

```bash
git add backend/quiz/tag_index.py backend/quiz/study_loop.py tests/test_study_loop_tags.py
git commit -m "$(cat <<'EOF'
feat(quiz): stitch vocab groups and tags into study-loop

EOF
)"
```

---

### Task 7: Frontend Daily Learn / Study Loop UI

**Files:**
- Create: `src/features/quiz/studyLoop/TagPicker.tsx`
- Create: `src/features/quiz/studyLoop/ReadCardPanel.tsx`
- Create: `src/features/quiz/studyLoop/QuestionEditor.tsx`
- Create: `src/features/quiz/studyLoop/LoopTab.tsx`
- Modify: `src/api/globalQuizClient.ts`
- Modify: `src/pages/quiz/ReviewHubPage.tsx`
- Modify: `src/components/dashboard/StudyLoopWidget.tsx`

**Interfaces:**
- Consumes: new quiz client functions below; tag summaries may include optional `due_count` and `pillar_weight` (default 1.0)
- Produces: Loop tab UX states `pick_tag | read | practice | edit_question`
- **TagPicker sort (optional, near-zero risk):** `score = (due_count || 0) * (pillar_weight || 1)` descending, then label. Static pillar weights from a tiny map (CAT appendix → Arithmetic/Algebra/… multipliers) — **metadata only**, not a second orchestrator / not DKT.
- **card_id:** API returns `path::topic_id`; all path-segment uses must `encodeURIComponent(cardId)`.
- **409 PATCH recovery:** toast + keep draft; **Reload latest** vs **Overwrite anyway** — never silent discard.

Client additions:

```typescript
export async function fetchStudyLoopTags(opts?: { q?: string; kind?: string }) {
  const qs = new URLSearchParams();
  if (opts?.q) qs.set("q", opts.q);
  if (opts?.kind) qs.set("kind", opts.kind);
  const q = qs.toString();
  return quizRequest<{ tags: Array<Record<string, unknown>> }>(`/study-loop/tags${q ? `?${q}` : ""}`);
}

export async function fetchStudyLoopReadCards(tag: string) {
  return quizRequest<{ items: Array<Record<string, unknown>>; count: number }>(
    `/study-loop/read-cards?tag=${encodeURIComponent(tag)}`
  );
}

export async function patchStudyLoopReadCard(
  cardId: string,
  body: { body_markdown: string; title?: string; expected_mtime?: number }
) {
  return quizRequest(`/study-loop/read-cards/${encodeURIComponent(cardId)}`, {
    method: "PATCH",
    body: JSON.stringify(body),
  });
}

export async function createStudyLoopSession(tag: string) {
  return quizRequest<{ session_id: string; read_completed: boolean; tag: string }>(
    `/study-loop/sessions`,
    { method: "POST", body: JSON.stringify({ tag }) }
  );
}

export async function markStudyLoopRead(sessionId: string) {
  return quizRequest(`/study-loop/sessions/${sessionId}/mark-read`, { method: "POST" });
}

export async function startStudyLoopPractice(sessionId: string, count = 5) {
  return quizRequest<{ session_id: string; domain: string; question: GlobalQuizQuestion }>(
    `/study-loop/sessions/${sessionId}/start-practice`,
    { method: "POST", body: JSON.stringify({ count }) }
  );
}
```

`LoopTab` flow:

1. `TagPicker` → set tag  
2. `createStudyLoopSession(tag)` + load read cards  
3. `ReadCardPanel` editable textarea; Save → `patchStudyLoopReadCard`  
4. Button “Mark read & practice” → `markStudyLoopRead` then `startStudyLoopPractice` → lift `session_id` to parent `active` quiz state (`mode: "resume"`)  
5. `QuestionEditor` drawer: list `GET /study-loop/questions?tag=`, patch open answers  

`ReviewHubPage`: extend `Tab` with `"loop"`; default from `?tab=loop`; show Loop as first primary tab after Due.

`StudyLoopWidget`: change due CTA to `/review?tab=loop` when `due_count===0`, else keep due; label “Daily Learn”.

- [ ] **Step 1: Write a lightweight client unit or compile check**

No Jest required if project lacks component tests — rely on `npm run build` in Task 9. Optionally add a tiny pure helper test if one exists for quiz utils.

- [ ] **Step 2: Implement components matching existing gloss-panel / Button patterns**

Keep layout consistent with ReviewHubPage cards; do not invent a new design system.

- [ ] **Step 3: Wire ReviewHubPage**

When practice returns, set:

```typescript
setActive({ mode: "resume", sessionId: practice.session_id });
```

Reuse existing `GlobalQuizRunner` mount.

- [ ] **Step 4: Manual sanity (dev server)**

Run: `run.bat` → open `http://localhost:5173/review?tab=loop` → pick `MT1-T02` → edit card → save → mark read → practice.

- [ ] **Step 5: Commit** (if authorized)

```bash
git add src/api/globalQuizClient.ts src/features/quiz/studyLoop src/pages/quiz/ReviewHubPage.tsx src/components/dashboard/StudyLoopWidget.tsx
git commit -m "$(cat <<'EOF'
feat(ui): Daily Learn Study Loop tab with read-then-practice

EOF
)"
```

---

### Task 8: Python IDE panel for coding kinds + `/code/run`

**Files:**
- Modify: `backend/quiz/router.py` — add `POST /code/run`
- Modify: `src/features/quiz/GlobalQuizRunner.tsx` — Run tests button calling API when `test_cases` present
- Modify: `src/components/study/PythonCodeBlock.tsx` **or** thin wrapper `CodingIdePanel.tsx` in `studyLoop/`
- Modify: `src/api/globalQuizClient.ts` — `runQuizCode`
- Test: `tests/test_quiz_code_run_api.py`

**Interfaces:**
- Consumes: `code_runner.grade_submission` / `run_cases`
- Produces: `{ all_passed, passed, total, outcomes, compile_error? }`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_quiz_code_run_api.py
from fastapi.testclient import TestClient
from backend.core.auth import get_current_user
from backend.main import app
from backend.models import User


def test_code_run_route_grades_addition():
    user = User(id=1, username="test", password_hash="hash")
    app.dependency_overrides[get_current_user] = lambda: user
    client = TestClient(app)
    try:
        r = client.post(
            "/api/quiz/code/run",
            json={
                "item": {
                    "entry_point": "add",
                    "test_cases": [
                        {"name": "t1", "input": [1, 2], "expected_output": 3},
                    ],
                },
                "code": "def add(a, b):\n    return a + b\n",
            },
        )
        assert r.status_code == 200
        body = r.json()
        assert body["all_passed"] is True
        assert body["passed"] == 1
    finally:
        app.dependency_overrides.pop(get_current_user, None)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_quiz_code_run_api.py::test_code_run_route_grades_addition -v`

Expected: FAIL `404` (route missing)

- [ ] **Step 3: Implement route**

```python
class CodeRunBody(BaseModel):
    code: str
    item: dict[str, Any] | None = None
    item_id: str | None = None


@router.post("/code/run")
def post_code_run(body: CodeRunBody, user: User = Depends(get_current_user)):
    from backend.quiz import code_runner as cr
    from backend.quiz import content_bank as cb

    _ = user
    item = body.item
    if item is None and body.item_id:
        found = cb.get_questions(question_ids=[body.item_id])
        item = found[0] if found else None
    if not item:
        raise HTTPException(status_code=400, detail="item or item_id required")
    correct, feedback, payload = cr.grade_submission(item, body.code)
    return {"correct": correct, "feedback": feedback, **payload}
```

Ensure `grade_submission` returns a dict payload with `outcomes` (adjust wrapper if it currently returns nested run result only — map `asdict(RunResult)`).

Frontend: for `question.format === "code"` show secondary button “Run tests” → `runQuizCode` → display pass/fail list under `PythonCodeBlock` (Pyodide Run stays for free stdout exploration).

- [ ] **Step 4: Run tests**

Run: `python -m pytest tests/test_quiz_code_run_api.py -v`

Expected: PASS

- [ ] **Step 5: Commit** (if authorized)

```bash
git add backend/quiz/router.py backend/quiz/code_runner.py tests/test_quiz_code_run_api.py src/api/globalQuizClient.ts src/features/quiz/GlobalQuizRunner.tsx
git commit -m "$(cat <<'EOF'
feat(quiz): wire /api/quiz/code/run and IDE test runner UI

EOF
)"
```

---

### Task 9: Verification + SESSION_LOG

**Files:**
- Modify: `docs/SESSION_LOG.md`
- Optionally: `AGENTS.md` one-line current focus pointer to Study Loop spec (only if still accurate)

- [ ] **Step 1: Run backend tests**

Run:

```bash
python -m pytest tests/test_study_loop_read_cards.py tests/test_study_loop_tags.py tests/test_study_loop_questions.py tests/test_study_loop_session.py tests/test_quiz_code_run_api.py tests/test_quiz_content_bank_api.py tests/test_note_topics.py -q
```

Expected: all PASS

- [ ] **Step 2: Broader quiz regression (recommended)**

Run: `python -m pytest tests/test_hybrid_math_bank.py tests/test_open_math_questions.py tests/test_adaptive_mathgen.py -q`

Expected: PASS

- [ ] **Step 3: Frontend build**

Run: `npm run build`

Expected: exit 0

- [ ] **Step 4: Update SESSION_LOG**

Add dated entry:

```markdown
## 2026-09-03 — Study Loop / Daily Learn (spec + impl)

**Done:**
- [x] Spec: `docs/superpowers/specs/2026-09-03-study-loop-design.md`
- [x] Plan: `docs/superpowers/plans/2026-09-03-study-loop.md`
- [ ] Tasks 1–8 implemented + verified (check when done)

**Try:** `/review?tab=loop` → pick `L5-T05` or `MT1-T02` → edit read card → mark read → practice → Due.
```

- [ ] **Step 5: Commit** (if authorized)

```bash
git add docs/SESSION_LOG.md
git commit -m "$(cat <<'EOF'
docs: note Study Loop verification in SESSION_LOG

EOF
)"
```

---

## Self-review (author checklist)

| Spec section | Task coverage |
|--------------|---------------|
| Read-card digest | Task 1 |
| Write-back A | Task 2 |
| Tag CRUD / rename / merge | Task 3 |
| Question CRUD / import / open answers | Task 4 |
| Forced read→practice + FSRS via handler | Task 5 (`resolve_practice_route`) |
| Vocab stitch | Task 6 |
| Daily Learn UI | Task 7 |
| Python IDE + `/code/run` | Task 8 |
| Acceptance / verify | Task 9 |
| Non-goals (no second SRS / no RAG) | Global Constraints + Task 5 uses `handler.start_session` |

Placeholder scan: no TBD/TODO left in task steps.  
Type consistency: `card_id` = `path::tag`; loop `session_id` distinct from quiz `session_id` (practice returns quiz `session_id` for runner); tag ids canonicalized via `canonicalize_topic_id` for note topics.

---

## Execution handoff

Plan complete and saved to `docs/superpowers/plans/2026-09-03-study-loop.md`. Two execution options:

1. **Subagent-Driven (recommended)** — fresh subagent per task, review between tasks  
2. **Inline Execution** — `superpowers:executing-plans` with checkpoints  

Which approach?
