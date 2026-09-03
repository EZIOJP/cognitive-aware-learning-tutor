# Math English Curriculum Pass — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Run a curriculum-first English math bank pass: import/merge multi-source questions with empty answers allowed, tag packs to sealed `MT*`, quarantine unmapped packs, write note stubs, seed one ReviewCard per question.

**Architecture:** New orchestrator `scripts/math_en_curriculum_pass.py` calls library helpers under `backend/math/curriculum_pass/` (or `scripts/lib/` if preferred — prefer `backend/math/` for pytest imports). Existing `scripts/import_math_aptitude_datasets.py` is refactored so per-source builders become importable helpers; the orchestrator owns merge, EN drop, map/tag/quarantine, stubs, and seed. No second quiz engine or SRS.

**Tech Stack:** Python 3, pytest, existing `content_bank` / `content_schemas` / `seed_content_cards` (extend or replace seed path for per-question cards), `note_topics.parse_note_topics`, SQLite ReviewCard.

## Global Constraints

- Spec: `docs/superpowers/specs/2026-09-03-math-en-curriculum-pass-design.md` (approved).
- Canonical tags: `MT{n}-Txx` only; `curriculum.json` sealed — no minting.
- Merge / identity: `(source, source_id)` → `id = math.{source}.{sanitized_source_id}` — **no `topic_id` in id**.
- Source vocabulary (exact): `sat` · `mathqa` · `hendrycks` · `saket` · `mathgenerator` · `deepmind` · `mathnet` · `authored`.
- Curated fields fill-empty-only; structural `note_topic_ids` / `tags` additive to computed curriculum set.
- Non-EN: drop + manifest; language field authoritative; else script heuristic only if len ≥ 24; else keep.
- Invalid `note_topic_ids`: strip + log (`note_topic_ids_normalized`).
- Cards: **one ReviewCard per question** (full `MT*` tag set in payload/tags) — not one per `(question, MT*)`, and not only one topic_pack card that hides the rule.
- Note files: fixed `MT{n}` → filename table; heading `## \`MT1-T07\` — Title`.
- Default: no `--clean-out`. Commits only when the user asks (commit steps included for authorized execution).
- ADR-001 / Study Loop wiring unchanged.

### Pre-flight (done)

- Heading regex in `backend/transcripts/note_topics.py` accepts optional backticks and separators `—` `-` `–` `:`.

### Seed path lock

Current `seed_content_cards` creates **one topic_pack card per `topic_id`**. Spec requires **one card per question**. This plan adds `seed_question_cards` (or equivalent) keyed by question `id`; do not treat topic_pack seeding as satisfying the spec.

---

## File structure map

| Path | Responsibility |
|------|----------------|
| `backend/math/curriculum_pass/__init__.py` | Package exports |
| `backend/math/curriculum_pass/constants.py` | Source vocab, `EN_HEURISTIC_MIN_CHARS=24`, module→note filename map, `_meta` paths |
| `backend/math/curriculum_pass/curriculum.py` | Load curriculum; reverse index; normalize topic_id |
| `backend/math/curriculum_pass/identity.py` | `make_question_id`, sanitize source_id, provenance fields |
| `backend/math/curriculum_pass/language.py` | EN decide + drop logging |
| `backend/math/curriculum_pass/merge.py` | Fill-empty-only merge by `(source, source_id)` |
| `backend/math/curriculum_pass/map_packs.py` | Map/quarantine/tag/`note_topic_ids` normalize |
| `backend/math/curriculum_pass/stubs.py` | Note stub ensure |
| `backend/math/curriculum_pass/seed.py` | One ReviewCard per question |
| `backend/math/curriculum_pass/summary.py` | Counters + `_meta` writers |
| `scripts/math_en_curriculum_pass.py` | CLI orchestrator |
| `scripts/import_math_aptitude_datasets.py` | Thin wrappers calling shared builders (no curriculum-pass flags) |
| `tests/test_math_curriculum_pass_*.py` | Unit/integration tests |
| `data/questions/math/_meta/` | `needs_topic.json`, `dropped_non_en.jsonl`, run summary |

---

### Task 1: Curriculum reverse index + constants

**Files:**
- Create: `backend/math/curriculum_pass/constants.py`
- Create: `backend/math/curriculum_pass/curriculum.py`
- Create: `backend/math/curriculum_pass/__init__.py`
- Test: `tests/test_math_curriculum_pass_curriculum.py`

**Interfaces:**
- Produces:
  - `SOURCES: frozenset[str]`
  - `EN_HEURISTIC_MIN_CHARS: int = 24`
  - `MODULE_NOTE_FILES: dict[str, str]`  # `"MT1"` → `"MT1_aptitude_interview_notes.md"`
  - `def normalize_topic_id(raw: str) -> str`
  - `def load_curriculum(path: Path | None = None) -> dict`
  - `def build_reverse_index(curriculum: dict) -> dict[str, set[str]]`  # normalized topic_id → set of MT*
  - `def all_curriculum_mt_ids(curriculum: dict) -> list[tuple[str, str]]`  # (note_topic_id, title) in order

- [ ] **Step 1: Write the failing test**

```python
# tests/test_math_curriculum_pass_curriculum.py
from backend.math.curriculum_pass.curriculum import (
    build_reverse_index,
    normalize_topic_id,
    load_curriculum,
)


def test_normalize_topic_id_trim_lower():
    assert normalize_topic_id("  Math.Aptitude.Sat-Algebra ") == "math.aptitude.sat-algebra"


def test_reverse_index_maps_prefer_to_mt(tmp_path):
    cur = {
        "levels": [
            {
                "steps": [
                    {
                        "note_topic_id": "MT1-T05",
                        "title": "Averages",
                        "prefer_topic_ids": ["math.aptitude.sat-data"],
                    },
                    {
                        "note_topic_id": "MT1-T07",
                        "title": "Time & work",
                        "prefer_topic_ids": ["math.aptitude.sat-data", "math.aptitude.gen-time-work"],
                    },
                ]
            }
        ]
    }
    idx = build_reverse_index(cur)
    assert idx[normalize_topic_id("math.aptitude.sat-data")] == {"MT1-T05", "MT1-T07"}
    assert idx[normalize_topic_id("math.aptitude.gen-time-work")] == {"MT1-T07"}
```

- [ ] **Step 2: Run test — expect FAIL** (module missing)

Run: `python -m pytest tests/test_math_curriculum_pass_curriculum.py -v`

- [ ] **Step 3: Implement constants + curriculum helpers**

```python
# backend/math/curriculum_pass/constants.py
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
CURRICULUM_PATH = ROOT / "data" / "questions" / "math" / "curriculum.json"
QUESTIONS_MATH = ROOT / "data" / "questions" / "math"
NOTES_MATH = ROOT / "data" / "notes" / "math"
META_DIR = QUESTIONS_MATH / "_meta"

SOURCES = frozenset(
    {"sat", "mathqa", "hendrycks", "saket", "mathgenerator", "deepmind", "mathnet", "authored"}
)
EN_HEURISTIC_MIN_CHARS = 24
MODULE_NOTE_FILES = {
    "MT1": "MT1_aptitude_interview_notes.md",
    "MT2": "MT2_algebra_notes.md",
    "MT3": "MT3_linear_algebra_ml_notes.md",
    "MT4": "MT4_calculus_ml_notes.md",
}
```

```python
# backend/math/curriculum_pass/curriculum.py
from __future__ import annotations
import json
from pathlib import Path
from backend.math.curriculum_pass.constants import CURRICULUM_PATH
from backend.transcripts.note_topics import canonicalize_topic_id


def normalize_topic_id(raw: str) -> str:
    return (raw or "").strip().lower()


def load_curriculum(path: Path | None = None) -> dict:
    p = path or CURRICULUM_PATH
    return json.loads(p.read_text(encoding="utf-8"))


def build_reverse_index(curriculum: dict) -> dict[str, set[str]]:
    out: dict[str, set[str]] = {}
    for level in curriculum.get("levels") or []:
        for step in level.get("steps") or []:
            mt = canonicalize_topic_id(str(step.get("note_topic_id") or "")) or str(
                step.get("note_topic_id") or ""
            ).strip()
            if not mt:
                continue
            for tid in step.get("prefer_topic_ids") or []:
                key = normalize_topic_id(str(tid))
                if not key:
                    continue
                out.setdefault(key, set()).add(mt)
    return out


def all_curriculum_mt_ids(curriculum: dict) -> list[tuple[str, str]]:
    seen: set[str] = set()
    rows: list[tuple[str, str]] = []
    for level in curriculum.get("levels") or []:
        for step in level.get("steps") or []:
            mt = canonicalize_topic_id(str(step.get("note_topic_id") or "")) or ""
            title = str(step.get("title") or mt).strip()
            if mt and mt not in seen:
                seen.add(mt)
                rows.append((mt, title))
    return rows
```

- [ ] **Step 4: Run tests — expect PASS**

Run: `python -m pytest tests/test_math_curriculum_pass_curriculum.py -v`

- [ ] **Step 5: Commit** (when user authorizes)

```bash
git add backend/math/curriculum_pass tests/test_math_curriculum_pass_curriculum.py
git commit -m "feat(math): curriculum reverse index for EN curriculum pass"
```

---

### Task 2: Identity + language helpers

**Files:**
- Create: `backend/math/curriculum_pass/identity.py`
- Create: `backend/math/curriculum_pass/language.py`
- Test: `tests/test_math_curriculum_pass_identity_language.py`

**Interfaces:**
- Produces:
  - `def sanitize_source_id(raw: str) -> str`
  - `def make_question_id(source: str, source_id: str) -> str`  # `math.{source}.{sanitized}`
  - `def attach_provenance(q: dict, source: str, source_id: str) -> dict`
  - `def decide_english(problem: str, *, language_field: str | None) -> tuple[bool, str]`  
    returns `(keep, reason)` where reason in `explicit_en|explicit_non_en|short_keep|script_drop|script_keep`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_math_curriculum_pass_identity_language.py
from backend.math.curriculum_pass.identity import make_question_id
from backend.math.curriculum_pass.language import decide_english


def test_id_from_source_pair_only():
    assert make_question_id("mathqa", "142") == "math.mathqa.142"
    assert "aptitude" not in make_question_id("mathqa", "142")
    assert make_question_id("mathqa", "142") != make_question_id("hendrycks", "142")


def test_explicit_language_skips_heuristic():
    keep, reason = decide_english("これは日本語の長い問題文ですよ本当に", language_field="ja")
    assert keep is False and reason == "explicit_non_en"


def test_short_stem_default_keep():
    keep, reason = decide_english("Solve: 3x+5=20", language_field=None)
    assert keep is True and reason == "short_keep"


def test_long_non_latin_script_drop():
    text = "これは数学の問題です。" * 5  # > 24 chars, mostly non-Latin letters
    keep, reason = decide_english(text, language_field=None)
    assert keep is False and reason == "script_drop"
```

- [ ] **Step 2: Run — expect FAIL**

Run: `python -m pytest tests/test_math_curriculum_pass_identity_language.py -v`

- [ ] **Step 3: Implement**

```python
# backend/math/curriculum_pass/identity.py
from __future__ import annotations
import re
from backend.math.curriculum_pass.constants import SOURCES

_SAFE = re.compile(r"[^a-zA-Z0-9._-]+")


def sanitize_source_id(raw: str) -> str:
    s = _SAFE.sub("_", (raw or "").strip())
    return s[:120] or "unknown"


def make_question_id(source: str, source_id: str) -> str:
    src = (source or "").strip().lower()
    if src not in SOURCES:
        raise ValueError(f"unknown source: {source!r}")
    return f"math.{src}.{sanitize_source_id(source_id)}"


def attach_provenance(q: dict, source: str, source_id: str) -> dict:
    out = dict(q)
    out["source"] = source
    out["source_id"] = str(source_id)
    out["id"] = make_question_id(source, str(source_id))
    return out
```

```python
# backend/math/curriculum_pass/language.py
from __future__ import annotations
import re
from backend.math.curriculum_pass.constants import EN_HEURISTIC_MIN_CHARS

_LETTER = re.compile(r"[^\W\d_]", re.UNICODE)
_LATIN = re.compile(r"[A-Za-z]")


def decide_english(problem: str, *, language_field: str | None) -> tuple[bool, str]:
    lang = (language_field or "").strip().lower()
    if lang:
        if lang in ("en", "english"):
            return True, "explicit_en"
        return False, "explicit_non_en"
    text = problem or ""
    compact = "".join(text.split())
    if len(compact) < EN_HEURISTIC_MIN_CHARS:
        return True, "short_keep"
    letters = _LETTER.findall(text)
    if not letters:
        return True, "script_keep"
    latin = sum(1 for ch in letters if _LATIN.match(ch))
    non_latin_ratio = 1.0 - (latin / len(letters))
    if non_latin_ratio > 0.30:
        return False, "script_drop"
    return True, "script_keep"
```

- [ ] **Step 4: Run — expect PASS**

- [ ] **Step 5: Commit** (when authorized)

---

### Task 3: Merge (fill-empty-only) + map/tag/quarantine

**Files:**
- Create: `backend/math/curriculum_pass/merge.py`
- Create: `backend/math/curriculum_pass/map_packs.py`
- Create: `backend/math/curriculum_pass/summary.py`
- Test: `tests/test_math_curriculum_pass_map_merge.py`

**Interfaces:**
- Produces:
  - `CURATED_FIELDS = ("answer", "solution_steps", "hint", "explanation")`
  - `def merge_question(existing: dict | None, incoming: dict) -> dict`
  - `def map_pack(pack: dict, reverse_index: dict[str, set[str]], curriculum_mts: set[str]) -> MapResult`
  - `MapResult` dataclass: `status: mapped|quarantined`, `pack: dict`, `multi_topic: bool`, `removed_note_topic_ids: list[str]`
  - `PassSummary` with counters including `note_topic_ids_normalized`, `packs_multi_topic`, etc.
  - `def write_needs_topic(rows: list[dict], path: Path) -> None`
  - `def append_dropped_non_en(row: dict, path: Path) -> None`

- [ ] **Step 1: Failing tests**

```python
# tests/test_math_curriculum_pass_map_merge.py
from backend.math.curriculum_pass.merge import merge_question
from backend.math.curriculum_pass.map_packs import map_pack
from backend.math.curriculum_pass.curriculum import normalize_topic_id


def test_merge_fill_empty_only():
    existing = {
        "id": "math.mathqa.1",
        "source": "mathqa",
        "source_id": "1",
        "answer": "42",
        "hint": "",
        "tags": ["old"],
    }
    incoming = {
        "id": "math.mathqa.1",
        "source": "mathqa",
        "source_id": "1",
        "answer": "99",
        "hint": "use algebra",
        "tags": ["new"],
    }
    out = merge_question(existing, incoming)
    assert out["answer"] == "42"
    assert out["hint"] == "use algebra"


def test_map_pack_additive_lockstep_and_multi():
    reverse = {
        normalize_topic_id("math.aptitude.sat-data"): {"MT1-T05", "MT1-T07"},
    }
    pack = {
        "topic": {
            "topic_id": "math.aptitude.sat-data",
            "note_topic_ids": ["MT1-T05", "L9-T01"],
            "title": "SAT data",
        },
        "questions": [
            {"id": "math.sat.1", "source": "sat", "source_id": "1", "problem": "x", "tags": ["MT1-T05"]},
        ],
    }
    result = map_pack(pack, reverse, curriculum_mts={"MT1-T05", "MT1-T07"})
    assert result.status == "mapped"
    assert result.multi_topic is True
    assert set(result.pack["topic"]["note_topic_ids"]) == {"MT1-T05", "MT1-T07"}
    assert "L9-T01" in result.removed_note_topic_ids
    assert set(result.pack["questions"][0]["tags"]) >= {"MT1-T05", "MT1-T07"}


def test_quarantine_when_not_in_index():
    pack = {
        "topic": {"topic_id": "math.orphan.pack", "note_topic_ids": [], "title": "x"},
        "questions": [],
    }
    result = map_pack(pack, {}, curriculum_mts=set())
    assert result.status == "quarantined"
```

- [ ] **Step 2: Run — expect FAIL**

- [ ] **Step 3: Implement merge + map_packs + summary writers**

Key rules in `map_pack`:
1. `computed = reverse_index.get(normalize_topic_id(topic_id), set())`
2. If empty → quarantine (leave pack dict unchanged for disk; status quarantined).
3. Else: `valid_existing = [x for x in note_topic_ids if x in curriculum_mts]`; `removed =` the rest; `union = sorted(set(valid_existing) | computed)`; set pack `note_topic_ids = union`; for each question add missing MT* to tags.
4. `multi_topic = len(computed) > 1`.

`merge_question`: for each curated field, keep existing if non-empty (lists: non-empty list wins); always prefer existing `id`/`source`/`source_id` when present.

- [ ] **Step 4: Run — expect PASS**

- [ ] **Step 5: Commit** (when authorized)

---

### Task 4: Note stubs

**Files:**
- Create: `backend/math/curriculum_pass/stubs.py`
- Test: `tests/test_math_curriculum_pass_stubs.py`

**Interfaces:**
- Produces: `def ensure_note_stubs(mt_rows: list[tuple[str, str]], *, notes_dir: Path) -> dict`  
  returns `{stubs_created, stubs_skipped_nonempty}`

- [ ] **Step 1: Failing test**

```python
# tests/test_math_curriculum_pass_stubs.py
from pathlib import Path
from backend.math.curriculum_pass.stubs import ensure_note_stubs
from backend.transcripts.note_topics import parse_note_topics


def test_stub_creates_heading_idempotent(tmp_path: Path):
    stats = ensure_note_stubs([("MT1-T07", "Time & work")], notes_dir=tmp_path)
    assert stats["stubs_created"] == 1
    path = tmp_path / "MT1_aptitude_interview_notes.md"
    text = path.read_text(encoding="utf-8")
    assert "## `MT1-T07` — Time & work" in text
    topics = parse_note_topics(text, min_body_chars=0)
    assert any(t.topic_id == "MT1-T07" for t in topics)
    stats2 = ensure_note_stubs([("MT1-T07", "Time & work")], notes_dir=tmp_path)
    assert stats2["stubs_created"] == 0
    # filled body preserved
    path.write_text(
        text.replace("TODO: fill notes", "Real notes about work rates."),
        encoding="utf-8",
    )
    ensure_note_stubs([("MT1-T07", "Time & work")], notes_dir=tmp_path)
    assert "Real notes about work rates." in path.read_text(encoding="utf-8")
```

- [ ] **Step 2: Run — expect FAIL**

- [ ] **Step 3: Implement** using `MODULE_NOTE_FILES` keyed by `MT{n}` prefix (`re.match(r"(MT\d+)", mt)`). Heading exact: `## \`{mt}\` — {title}`. Stub body: `TODO: fill notes\n`. If heading exists and body non-empty → skip. Use `backend.quiz.atomic_io.atomic_write_text` if available.

- [ ] **Step 4: Run — expect PASS**

- [ ] **Step 5: Commit** (when authorized)

---

### Task 5: Per-question ReviewCard seed

**Files:**
- Create: `backend/math/curriculum_pass/seed.py`
- Modify: `backend/quiz/review_cards.py` only if a tiny shared helper is cleaner — prefer new function in `seed.py` that uses `upsert`-style logic mirroring `seed_content_cards` but **per question**.
- Test: `tests/test_math_curriculum_pass_seed.py`

**Interfaces:**
- Produces: `def seed_mapped_questions(db, *, user_id: int, packs: list[dict]) -> int`  
  For each question in each **mapped** pack: one `ReviewCard` with `item_key = math:{question_id}`, payload including `tags` (full MT* set), `domain="math"`. Skip quarantined packs. Idempotent update of payload/label if key exists.

- [ ] **Step 1: Failing test** (use sqlite session fixture from existing quiz tests)

```python
def test_one_card_per_question_not_per_mt(db_session, user_id):
    from backend.math.curriculum_pass.seed import seed_mapped_questions
    from backend.models.review_card import ReviewCard

    pack = {
        "topic": {"topic_id": "math.aptitude.sat-data", "title": "SAT", "note_topic_ids": ["MT1-T05", "MT1-T07"]},
        "questions": [
            {
                "id": "math.sat.99",
                "source": "sat",
                "source_id": "99",
                "problem": "Mean of 1,2,3?",
                "answer": "2",
                "tags": ["MT1-T05", "MT1-T07", "sat"],
            }
        ],
    }
    n = seed_mapped_questions(db_session, user_id=user_id, packs=[pack])
    assert n == 1
    rows = db_session.query(ReviewCard).filter(ReviewCard.user_id == user_id).all()
    assert len(rows) == 1
    assert "math.sat.99" in rows[0].item_key
```

- [ ] **Step 2–4: Implement + pass** (reuse `srs_mod.SrsState()` like `seed_content_cards`)

- [ ] **Step 5: Commit** (when authorized)

---

### Task 6: Orchestrator CLI + wire source helpers

**Files:**
- Create: `scripts/math_en_curriculum_pass.py`
- Modify: `scripts/import_math_aptitude_datasets.py` — extract pure builder functions importable without wiping; keep CLI behavior. Orchestrator calls builders then `merge`/`map`/`stubs`/`seed`.
- Test: `tests/test_math_curriculum_pass_orchestrator.py` (tmp_path end-to-end on 1–2 fixture packs, no HF required)

**Interfaces:**
- CLI: `python scripts/math_en_curriculum_pass.py [--skip-import] [--skip-seed] [--user-id N]`
- Default: no clean-out; writes `_meta/needs_topic.json`, `_meta/dropped_non_en.jsonl`, prints all summary buckets.

**Pipeline order (exact):**

1. Load curriculum → reverse index  
2. Import/refresh sources (or `--skip-import` to map existing bank only)  
3. For each pack JSON under `data/questions/math/**` (skip `_meta`, `_user` optional include): EN already applied at import; map/tag/quarantine; write pack if mapped  
4. Stubs for all curriculum MT*  
5. Seed mapped packs  
6. Summary  

- [ ] **Step 1: Fixture E2E test** with two packs (one mapped, one orphan), one short EN stem, one long non-Latin drop logged.

- [ ] **Step 2: Implement orchestrator**

Minimal skeleton:

```python
# scripts/math_en_curriculum_pass.py
"""Curriculum-first English math bank pass. See docs/superpowers/specs/2026-09-03-math-en-curriculum-pass-design.md"""
from __future__ import annotations
import argparse
# load curriculum, optional import helpers, walk packs, map, stubs, seed, print summary
```

When adapting importers: every emitted question must go through `attach_provenance(source, source_id)` and `decide_english` before write; empty answer → `answer_format="open"`.

- [ ] **Step 3: Run unit suite**

Run: `python -m pytest tests/test_math_curriculum_pass_*.py -v`  
Expected: PASS

- [ ] **Step 4: Validate bank**

Run: `python -m backend.quiz.content_bank --validate`  
Expected: 0 schema errors on kept packs (quarantine files may still load if left on disk — ensure quarantined packs still schema-valid or live under a skipped path; prefer leave in place and valid).

- [ ] **Step 5: Commit** (when authorized)

---

### Task 7: Docs touch-up + owner dry-run checklist

**Files:**
- Modify: `docs/MATH_DAILY_PATH_ROADMAP.md` — point regenerate command to `math_en_curriculum_pass.py`
- Modify: `docs/QUESTION_CONTENT_FORMAT.md` — note `source` / `source_id` / id shape `math.{source}.{source_id}`
- Optional: `docs/SESSION_LOG.md` after verified run

- [ ] **Step 1: Update roadmap command block**

```bat
python scripts/math_en_curriculum_pass.py
```

- [ ] **Step 2: Manual dry-run checklist**

1. `python scripts/math_en_curriculum_pass.py --skip-import` on current bank (map/stubs only) — inspect summary.  
2. Spot-check `_meta/dropped_non_en.jsonl` and `needs_topic.json`.  
3. Confirm `packs_multi_topic` and `note_topic_ids_normalized` printed.  
4. Open one note file — headings parse in Study Loop.  
5. DB: one `ReviewCard` per seeded question id after seed step.  
6. Full import run when datasets available (no `--clean-out`).

- [ ] **Step 3: Commit docs** (when authorized)

---

## Spec coverage checklist

| Spec requirement | Task |
|------------------|------|
| Sealed curriculum / reverse index | 1 |
| `(source, source_id)` → `math.{source}.{id}` no topic in id | 2, 6 |
| Source vocabulary | 2 constants |
| EN field → floor → script; manifest | 2, 3, 6 |
| Additive note_topic_ids + tags lockstep | 3 |
| `note_topic_ids_normalized` logged | 3, 6 |
| Quarantine `_meta/needs_topic.json` | 3, 6 |
| `packs_multi_topic` | 3, 6 |
| Fill-empty curated fields | 3, 6 |
| Note stubs fixed module map + heading | 4 |
| One card per question | 5 |
| Orchestrator script (not aptitude CLI flags) | 6 |
| Docs | 7 |

## Plan self-review

- No TBD placeholders in tasks.  
- Seed multiplicity explicitly tasked (Task 5) — does not inherit broken `seed_content_cards` topic_pack semantics.  
- Id example matches source vocab (`math.mathqa.142`).  
- Invalid note_topic_ids removal has counter + log in Task 3.
