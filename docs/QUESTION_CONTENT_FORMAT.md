# Question content format

**Status:** active contract · **Schema version:** 1

This is the loader contract for **question content datasets** that plug into the unified
Questions surface (`/questions`) and the existing `/api/quiz` engine + FSRS `ReviewCard` SRS.

Content authors (math roadmap, coding bank) only write JSON files. The loader
(`backend/quiz/content_bank.py`) reads them, validates against
`backend/quiz/content_schemas.py`, turns them into quiz items for the existing runner, and
seeds `ReviewCard`s keyed by `topic_id`.

> Nothing here introduces a second quiz runner or a second SRS. Items produced by this loader
> flow through `POST /api/quiz/start` → `submit_answer` → `upsert_review_card`, exactly like
> lecture-note MCQs and vocab.

---

## 1. Where files live

```text
data/questions/
├── math/
│   ├── aptitude/             # SAT · MathQA · SAKET · authored (time-work, …)
│   ├── generated/            # mathgenerator drills
│   ├── deepmind/             # school arithmetic / gcd / prob
│   ├── aiml/                 # vector / ML-entry drills
│   ├── competition/          # Hendrycks MATH subjects
│   ├── olympiad/             # MathNet
│   ├── _user/                # Study Loop CRUD / imports (one file per topic_id)
│   └── curriculum.json       # Daily Path unlock order (skipped by loader)
├── coding/                   # (optional) numpy / pandas / ML coding packs + `_user/`
├── mcq/                      # authored or imported multiple-choice packs + `_user/`
└── coding_mcq/               # multiple-choice over code approaches + `_user/`
```

Rules:

- **One file = one topic.** The file's `topic.topic_id` is the SRS grouping key.
- Sub-folders under each kind are free-form and used only for human organization
  (the loader walks recursively). Roadmap position comes from `topic.stage` / `topic.path`,
  never from the folder name.
- **Study Loop CRUD / imports** write new packs only at
  `data/questions/{kind}/_user/{safe_topic_id}.json` (`safe_topic_id` = `topic_id` with
  unsafe path characters replaced by `_`). Existing question `id`s are updated in the file
  that already owns them (including hand-authored packs). Re-import is idempotent: same
  `id` updates in place, never duplicates.
- Folders whose names start with `_` are skipped by the loader **except** `_user`.
- File name should be the kebab-case tail of `topic_id`. Not enforced.
- Encoding: UTF-8, `.json`, one JSON object per file.
- Path constant: `backend.paths.QUESTIONS_DIR` (`data/questions`). Do not hardcode paths.

Invalid files are **skipped, not fatal** — the loader reports them in
`GET /api/quiz/content/catalog` under `errors[]` so a half-written dataset never breaks the app.

---

## 2. Shared envelope

Every file has the same top-level shape:

| Field | Type | Required | Notes |
|---|---|---|---|
| `schema_version` | int | yes | `1` |
| `kind` | `"math" \| "coding" \| "mcq" \| "coding_mcq"` | yes | Item kind for every question in the file |
| `topic` | object | yes | See below |
| `questions` | array | yes | Min 1 |

### `topic`

| Field | Type | Required | Notes |
|---|---|---|---|
| `topic_id` | string | yes | Stable slug, `[a-z0-9._-]`, e.g. `math.aptitude.lcm-hcf`. **Never reuse or renumber.** |
| `title` | string | yes | Human label shown in the topic picker |
| `stage` | string | no | Roadmap stage, e.g. `foundations`, `core`, `advanced` |
| `path` | string[] | no | Breadcrumb: roadmap stage → topic → subtopic |
| `track` | string | no | `aiml` \| `aptitude` (math) or `numpy` \| `pandas` \| `ml` … (coding) |
| `prerequisites` | string[] | no | Other `topic_id`s |
| `note_topic_ids` | string[] | no | Note topic tags (`L{n}-Txx` or `MT{n}-Txx`) this topic backs — links notes to practice |
| `description` | string | no | One-line scope |

`note_topic_ids` is the bridge to lecture notes: an `L04-T02` note section can offer
"practice this" because a content topic claims `L04-T02`.

### Question fields shared by both kinds

| Field | Type | Required | Notes |
|---|---|---|---|
| `id` | string | yes | Globally unique, stable. For curriculum-pass imports: `math.{source}.{source_id}` (e.g. `math.mathqa.142`) — **do not** embed pack `topic_id` in `id`. Older packs may still use `<topic_id>.q001`. |
| `source` | string | no | Upstream name (`sat`, `mathqa`, `hendrycks`, `saket`, `mathgenerator`, `deepmind`, `mathnet`, `authored`) |
| `source_id` | string | no | Upstream id; with `source` forms the merge key |
| `difficulty` | `"easy" \| "medium" \| "hard"` | no | Default `medium` |
| `explanation` | string | no | Shown after answering |
| `hint` | string | no | Behind the "Show hint" button |
| `tags` | string[] | no | Free-form |

---

## 3. `kind: "math"`

Extra question fields:

| Field | Type | Required | Notes |
|---|---|---|---|
| `problem` | string | yes | The prompt. Markdown + `$latex$` allowed |
| `answer` | string | yes | Ground truth. Empty string = open / proof-style (self-check; fill later via Study Loop PATCH). When auto-graded, SymPy equivalence (`backend/math/answer_grade.py`) matches `1/2`, `0.5`, and `2^-1`. **Unit-free:** put units in the problem text (or optional display-only `unit` field); never `"5 days"` / `"₹240"` as `answer` when `answer_format` is `number`/`expression`. Open items that later get an answer must still follow this rule. |
| `answer_format` | `"number" \| "expression" \| "text" \| "open"` | no | Default `expression`. Empty `answer` is stored as `open`. `text` falls back to normalized string compare. `open` uses self-check UX (no auto-grade key). |
| `unit` | string | no | Display-only unit label (e.g. `days`, `₹`). Not graded |
| `solution_steps` | string[] | no | Revealed one step at a time in the runner |

```json
{
  "schema_version": 1,
  "kind": "math",
  "topic": {
    "topic_id": "math.aptitude.lcm-hcf",
    "title": "LCM & HCF",
    "stage": "foundations",
    "path": ["Aptitude Math", "Number Theory", "LCM & HCF"],
    "track": "aptitude",
    "prerequisites": ["math.aptitude.factors-multiples"],
    "note_topic_ids": [],
    "description": "Least common multiple and highest common factor, including word problems."
  },
  "questions": [
    {
      "id": "math.aptitude.lcm-hcf.q001",
      "problem": "Find the HCF of 84 and 126.",
      "answer": "42",
      "answer_format": "number",
      "difficulty": "easy",
      "solution_steps": [
        "Prime factorise: 84 = 2^2 · 3 · 7 and 126 = 2 · 3^2 · 7.",
        "Take the lowest power of each shared prime: 2^1 · 3^1 · 7^1.",
        "So HCF = 2 · 3 · 7 = 42."
      ],
      "explanation": "HCF multiplies the lowest shared prime powers; LCM takes the highest.",
      "hint": "Factorise both numbers into primes first.",
      "tags": ["hcf", "prime-factorisation"]
    }
  ]
}
```

---

## 4. `kind: "coding"`

Extra question fields:

| Field | Type | Required | Notes |
|---|---|---|---|
| `title` | string | yes | Short label |
| `prompt` | string | yes | Task description (markdown) |
| `language` | string | no | Default `python`. **Only `python` is executable today** — other languages load but are graded as "submitted for review" |
| `entry_point` | string | no | Function the tests call. Omit for script/stdout mode |
| `starter_code` | string | yes | Pre-filled editor content |
| `solution` | string | no | Reference solution (never sent to the client before submitting) |
| `setup_code` | string | no | Runs before the user's code (e.g. `import pandas as pd`) |
| `test_cases` | array | yes | Min 1. See below |

### `test_cases[]`

| Field | Type | Required | Notes |
|---|---|---|---|
| `name` | string | no | Defaults to `test_<n>` |
| `input` | array | yes* | Positional args passed to `entry_point`. Use `[]` for no args |
| `kwargs` | object | no | Keyword args passed to `entry_point` |
| `expected_output` | any | yes* | JSON value compared against the return value |
| `stdin` | string | no | Script mode: fed to stdin |
| `expected_stdout` | string | no | Script mode: compared to stdout (trailing whitespace stripped) |
| `is_edge_case` | bool | no | Default `false`. Edge cases are shown in their own group in the run-tests panel |
| `description` | string | no | Why this case exists — surfaced to the user on failure |
| `hidden` | bool | no | Default `false`. Hidden cases are graded but their input/expected are not shown before submit |

\* `input` + `expected_output` are required in **call mode** (`entry_point` set).
In **script mode** (no `entry_point`) use `stdin` / `expected_stdout` instead.

**Comparison rules** (`backend/quiz/code_runner.py`):

1. The return value is JSON-normalized (numpy scalars/arrays → lists, pandas Series/DataFrame →
   `to_dict()`, tuples → lists, sets → sorted lists) and compared to `expected_output`.
2. Floats compare with a relative tolerance of `1e-6`.
3. Script mode compares `stdout` line-by-line with trailing whitespace stripped.

**Grading:** a coding question is `correct` only when **every** test case passes (including
edge cases). Partial results (`tests_passed` / `tests_total`) come back in the feedback either way.

```json
{
  "schema_version": 1,
  "kind": "coding",
  "topic": {
    "topic_id": "coding.pandas.groupby",
    "title": "pandas GroupBy aggregation",
    "stage": "core",
    "path": ["Data Wrangling", "pandas", "GroupBy"],
    "track": "pandas",
    "note_topic_ids": ["L05-T03"]
  },
  "questions": [
    {
      "id": "coding.pandas.groupby.q001",
      "title": "Mean score per group",
      "prompt": "Implement `mean_by_group(rows)` where `rows` is a list of `[group, score]` pairs. Return a dict mapping each group to its mean score, rounded to 2 decimals. An empty input returns an empty dict.",
      "language": "python",
      "entry_point": "mean_by_group",
      "difficulty": "medium",
      "setup_code": "import pandas as pd",
      "starter_code": "def mean_by_group(rows):\n    # rows: list of [group, score]\n    ...\n",
      "solution": "def mean_by_group(rows):\n    if not rows:\n        return {}\n    df = pd.DataFrame(rows, columns=['g', 'score'])\n    return {k: round(v, 2) for k, v in df.groupby('g')['score'].mean().items()}\n",
      "explanation": "groupby(...).mean() aggregates per key; guard the empty frame because groupby on no rows yields an empty Series.",
      "hint": "Build a DataFrame first, then groupby('g')['score'].mean().",
      "test_cases": [
        {
          "name": "two_groups",
          "input": [[["a", 1], ["a", 3], ["b", 10]]],
          "expected_output": { "a": 2.0, "b": 10.0 },
          "is_edge_case": false,
          "description": "Typical case with uneven group sizes."
        },
        {
          "name": "empty_input",
          "input": [[]],
          "expected_output": {},
          "is_edge_case": true,
          "description": "Empty input must return {} rather than raising on an empty groupby."
        },
        {
          "name": "single_row_group",
          "input": [[["z", 7]]],
          "expected_output": { "z": 7.0 },
          "is_edge_case": true,
          "description": "A group of one — mean equals the only value."
        }
      ],
      "tags": ["pandas", "groupby"]
    }
  ]
}
```

---

## 5. `kind: "mcq"`

Multiple-choice (lecture-style or imported). Graded by `answer_index`.

| Field | Type | Required | Notes |
|---|---|---|---|
| `question` | string | yes | Stem |
| `options` | string[] | yes | Min 2 |
| `answer_index` | int | yes | 0-based index into `options` |

Markdown import (Study Loop): split on `^Q.`, options are `-` lines; `*` or `(*)` prefix marks the correct option.

```json
{
  "schema_version": 1,
  "kind": "mcq",
  "topic": {
    "topic_id": "mcq.loop.hcf",
    "title": "HCF",
    "note_topic_ids": ["MT1-T02"]
  },
  "questions": [
    {
      "id": "mcq.loop.hcf.q001",
      "question": "What is HCF of 8 and 12?",
      "options": ["2", "4", "8", "24"],
      "answer_index": 1
    }
  ]
}
```

---

## 6. `kind: "coding_mcq"`

Multiple-choice over approaches or snippets. Optional `starter_code` for exploration; grade by `answer_index`.

| Field | Type | Required | Notes |
|---|---|---|---|
| `prompt` | string | yes | Stem |
| `options` | string[] | yes | Min 2 |
| `answer_index` | int | yes | 0-based |
| `starter_code` | string | no | Pre-filled editor; not graded |

---

## 7. How the loader consumes this

| Step | Where |
|---|---|
| Validate + parse | `backend/quiz/content_schemas.py` (Pydantic v2) |
| Walk `data/questions/**`, build an in-process index | `backend/quiz/content_bank.py` → `load_catalog()` |
| Catalog for the UI topic picker | `GET /api/quiz/content/catalog` |
| Turn questions into runner items | `content_bank.build_quiz_items(kind=…, topic_id=…, count=…)` |
| Seed FSRS cards by `topic_id` | `POST /api/quiz/content/import` → `review_cards.seed_content_cards()` |
| Practice a topic | `POST /api/quiz/start` with `{"domain": "coding"\|"math", "config": {"topic_id": "…", "count": 5}}` |

The loader is cached by file mtime, so dropping new JSON in `data/questions/` shows up on the
next catalog fetch — no restart needed.

### Item shape the engine sees

The loader normalizes kinds into the existing quiz item shape, so nothing downstream
changes:

```python
# coding
{"kind": "coding", "id": "...", "title": "...", "prompt": "...", "starter_code": "...",
 "language": "python", "entry_point": "...", "test_cases": [...], "solution": "...",
 "explanation": "...", "topic_id": "coding.pandas.groupby", "difficulty": "medium"}

# math
{"kind": "math", "id": "...", "prompt": "<problem>", "expected_answer": "<answer>",
 "answer_format": "number|expression|text|open", "solution_steps": [...],
 "topic": "math.aptitude.lcm-hcf", "topic_id": "...",
 "difficulty": "easy", "hint": "...", "explanation": "..."}

# mcq
{"kind": "mcq", "id": "...", "question": "...", "options": [...], "answer_index": 0,
 "topic_id": "...", "note_topic_ids": [...], "content_kind": "mcq"}

# coding_mcq
{"kind": "coding_mcq", "id": "...", "prompt": "...", "options": [...], "answer_index": 0,
 "starter_code": "...", "topic_id": "...", "content_kind": "coding_mcq"}
```

`expected_answer` is the field name the existing math grader already reads — the loader maps
`answer` → `expected_answer` for you.

---

## 8. Authoring checklist

- [ ] `schema_version: 1` and `kind` set
- [ ] `topic.topic_id` is stable, lowercase, and unique across all files
- [ ] Every question `id` is unique (prefer `math.{source}.{source_id}` for imported items)
- [ ] Math: empty `answer` is allowed with `answer_format: open`; otherwise SymPy-parseable when `number`/`expression`
- [ ] Refresh English curriculum mapping (optional):

```bat
python scripts/math_en_curriculum_pass.py --skip-seed
```

- [ ] Coding: at least one non-edge case **and** at least one `is_edge_case: true` case
- [ ] Coding: `solution` actually passes its own `test_cases`
- [ ] Validate before hand-off:

```bat
python -m backend.quiz.content_bank --validate
```

That prints one line per file with question counts, and a non-zero exit if any file is invalid.
