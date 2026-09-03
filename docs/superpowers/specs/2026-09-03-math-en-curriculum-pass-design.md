# Math English curriculum pass — Design

**Date:** 2026-09-03  
**Status:** approved for implementation planning (Approach A + quarantine)  
**Related:** ADR-001 · `docs/QUESTION_CONTENT_FORMAT.md` · `docs/MATH_DAILY_PATH_ROADMAP.md` · `docs/superpowers/specs/2026-09-02-daily-path-math-mt-design.md` · `docs/superpowers/specs/2026-09-03-study-loop-design.md`

## Goal

Curriculum-first pass over the math question bank so keepable items are **English-only**, tagged with canonical **`MT{n}-Txx`**, linked via pack `note_topic_ids`, backed by **note stubs** you fill later, and **seedable** into existing FSRS `ReviewCard`s — without a second tag system, bank, quiz engine, or SRS.

Populate **everything** that is real English content even when `answer` / `solution_steps` / `hints` are empty. Enrich answers and prose later. Code / DA / DS playground is **out of scope**.

## Approach

**A — Curriculum-first** (chosen). Walk sealed `data/questions/math/curriculum.json`. Map packs via reverse index of `prefer_topic_ids` → step `note_topic_id`. Do not mint new `MT*` ids this sprint. Content with no clean home → **explicit quarantine**, not silent drop and not nearest-guess placement.

Rejected:

- **B** — Source-first taxonomy rewrite (breaks live Daily Path / Study Loop / FSRS ids).
- **C** — Dual bank under `_en/` (second source of truth / parallel id failure mode).

---

## 1. Goals, non-goals, success

### In scope

- English-only filter: **drop** non-English (not quarantine).
- Tag hygiene: mapped questions carry curriculum `MT*` in `tags`; pack `note_topic_ids` stay in lockstep with those tags.
- Note stubs under `data/notes/math/` for every **curriculum** `MT*`.
- Keep items with empty `answer` / steps / hints (`answer_format: "open"` when answer empty).
- Seed ReviewCards for mapped packs via existing `content_bank` / `seed_content_cards`.
- Quarantine packs with no curriculum home; surface counts in run summary + `_meta` manifest.
- Fill-empty-only for curated content fields; structural metadata follows additive computed truth (below).

### Out of scope

- Code / data-analysis / data-structures playground.
- Rewriting Daily Path or Study Loop ids.
- Filling answers, solution steps, or full note prose.
- Dual bank or parallel slug-tag system.
- Silent drop of unmapped packs; silent nearest-guess `MT*` placement.
- Minting new `MT*` mid-pass (`curriculum.json` is sealed; new sub-topics = curriculum edit).
- Per-question topic re-homing / splitting mixed packs.

### Success criteria

1. Every curriculum `MT*` has a parseable note heading in `data/notes/math/`.
2. Mapped packs: `note_topic_ids` equals the union of (existing **valid** curriculum ids already on the pack) and (computed set from reverse index); every kept question’s `tags` include that same full `MT*` set.
3. Quarantine list + summary: `kept` · `dropped_non_en` · `quarantined_unmapped` · `packs_multi_topic` · `note_topic_ids_normalized` · stub/card counters.
4. `content_bank` validate + seed for mapped topics only; Study Loop tag stitch still uses `MT*`.
5. Re-run is safe: no clobber of non-empty curated fields; no duplicate note files from slug drift; **one ReviewCard per question**.

---

## 2. Identity, mapping, quarantine

### Sealed curriculum

`data/questions/math/curriculum.json` is the only source of `MT*` ids this pass. Build reverse index:

```text
normalize(topic_id) → { note_topic_id, … }
```

from each step’s `prefer_topic_ids` → that step’s `note_topic_id`. Matching is **lowercase + trim** (and otherwise exact). No new `MT*` from ingest.

### Composite identity key

All identity matching (import merge, fill-empty-only, per-question tag ops) uses:

```text
(source, source_id)
```

never bare `id` alone.

- **`source`**: stable string naming the upstream (e.g. `sat`, `mathqa`, `hendrycks`, `saket`, `mathgenerator`, `deepmind`, `mathnet`, `authored`).
- **`source_id`**: upstream’s own id string (may be numeric/short).

**Storage (required on every question object written by this pass):**

- `source` and `source_id` as explicit fields (or under a fixed `provenance` object — one shape, used everywhere).
- Canonical bank `id` is derived **only** from `(source, source_id)` — e.g. `math.{source}.{source_id}` (sanitize `source_id` for path-safe characters). **Do not** embed `topic_id`, pack path, or curriculum `MT*` in `id`. Topic membership lives only in `note_topic_ids` / `tags` so remaps (quarantine → curriculum later, or future pack splits) do not force id renames or break ReviewCard / merge keys.

**Canonical `source` vocabulary** (use these exact strings everywhere — composite key, ids, manifests):

`sat` · `mathqa` · `hendrycks` · `saket` · `mathgenerator` · `deepmind` · `mathnet` · `authored`

Example: MathQA upstream id `142` → `id` = `math.mathqa.142` (not `math.aptitude.mathqa-general.q0142`).

If two sources both emit `"142"`, they remain distinct rows. Tag/`note_topic_ids` ops never splice across sources.

### Granularity

| Decision | Level | Rule |
|----------|--------|------|
| Has an `MT*` home? | **Pack** (`topic.topic_id`) | ≥1 curriculum `prefer_topic_ids` hit after normalize → **mapped**; else → **quarantine whole pack**. |
| English? | **Question** | Non-English → **drop** (not quarantine). |
| Wrong subtopic inside mapped pack? | **Out of scope** | No per-question re-home this sprint. |

### Mapped pack write rules

- **`note_topic_ids` (structural):** additive — union of (existing entries that are valid curriculum `MT*` ids) and (computed set for this `topic_id`). Never invent ids. Drop invalid non-curriculum ids from the pack’s list when normalizing (they are not quarantined content; they are bad metadata). **Every removed id is logged** — increment summary counter `note_topic_ids_normalized` and append a line to the run output / `_meta` summary (pack `topic_id`, `path`, `removed: [...]`). Not silent.
- **Question `tags` (structural):** ensure every id in that union appears in `tags` (add missing; do not remove other existing tags).
- **Curated fields:** `answer`, `solution_steps`, `hint`, `explanation` — **fill-empty-only**; never overwrite non-empty values.
- Pack and question structural sets stay in **lockstep** (same full `MT*` set on pack `note_topic_ids` and on each kept question’s tags for those curriculum ids).

### `packs_multi_topic`

If computed set size **> 1** for a pack, flag it in the summary (`packs_multi_topic`) and optionally on the `_meta` row. Still mapped; still seeded. Visibility only — no silent skip. (Coarse catch-all `topic_id`s that appear under multiple curriculum steps are the expected trigger.)

### Quarantine (unmapped packs)

- Do not rewrite for Study Loop linkage, do not create note stubs from them, do not seed ReviewCards.
- Record in `data/questions/math/_meta/needs_topic.json` (loader skips `_`-prefixed dirs except `_user`):

```json
{ "topic_id": "…", "path": "…", "question_count": 123, "reason": "no_curriculum_prefer" }
```

(`question_count` = actual questions in that pack.) Pack JSON may remain on disk untouched (visible backlog, not deleted).

### Non-English drop (safe)

**Constant:** `EN_HEURISTIC_MIN_CHARS = 24` (non-whitespace characters in problem text).

**Precedence**

1. If the source row has an **explicit language field** → that field is authoritative; **skip** heuristics. Non-`en`/`english`/empty-unknown → drop when the field clearly names another language; empty/missing field → fall through.
2. Else if problem text length **&lt; `EN_HEURISTIC_MIN_CHARS`** → **default-keep** (no heuristic).
3. Else apply a **script heuristic only**: drop if the share of letters in non-Latin scripts exceeds a fixed threshold (e.g. &gt; 30% of letter characters). Do **not** use fuzzy “language ID confidence” models. When in doubt after the script check → **keep**.

**Logging**

- Every dropped non-EN item is listed in the run summary manifest (e.g. `_meta/dropped_non_en.jsonl` or summary section) with `source`, `source_id`, and a **snippet of source text** for spot-check. Drop is recoverable only via re-import from upstream + manifest review — hence the floor and logging.

Never write non-EN drops into `needs_topic.json`.

---

## 3. Note stubs & ReviewCard seeding

### Note files (stable module map)

One markdown file per **module id** `MT{n}`, from a **fixed table** keyed by module id — **not** slugified curriculum titles:

| Module id | Filename (stable) |
|-----------|-------------------|
| `MT1` | `MT1_aptitude_interview_notes.md` |
| `MT2` | `MT2_algebra_notes.md` |
| `MT3` | `MT3_linear_algebra_ml_notes.md` |
| `MT4` | `MT4_calculus_ml_notes.md` |
| … | Extend table explicitly when curriculum adds `MT5+` modules |

Create the file if missing. Never derive the path from title text (avoids `MT1_aptitude.md` vs `MT1_Aptitude.md` orphans).

### Heading format (Study Loop parse target)

Literal form (aligned with `backend/transcripts/note_topics.py`):

```markdown
## `MT1-T07` — Time & work
```

- Topic id optional backticks; separator one of `—` / `-` / `–` / `:`; title = curriculum step `title`.
- Spec and stubs use this form **verbatim** (no alternate “`## MT1-T07 Time & Work`” without separator).
- **Parser pre-flight (confirmed 2026-09-03):** `backend/transcripts/note_topics.py` `_LID_IN_HEADING` is `` `?({MT|L}…)`?\s*(?:—|-|–|:)\s*(.+)$ `` — optional backticks and all four separators are accepted.

### Stub body rules

- For **every** curriculum step `note_topic_id`: ensure heading exists.
- Missing section → append stub (heading + short “TODO: fill notes” body only).
- Existing section with **non-empty** body → leave body untouched.
- Quarantined packs → no headings invented from their content.
- Curriculum tags with zero mapped questions after the pass → still get a stub heading.

### ReviewCard seeding

- Use existing `content_bank.import_content` / `seed_content_cards` for **mapped** pack `topic_id`s only.
- Domain `math`; no second SRS.
- **One card per question**, with `tags` = full `MT*` set for that pack. **Not** one card per `(question, MT*)` pair (no N× FSRS weight for `packs_multi_topic`).
- `packs_multi_topic` packs are seeded the same way (one card / question); the summary flag is the warning.
- Empty answers still seed (`open` / incomplete OK).
- Idempotent re-seed by existing item keys; does not wipe unrelated cards.

---

## 4. Pipeline & orchestrator

### Entry point

**New script:** `scripts/math_en_curriculum_pass.py`  

Sole curriculum-wide orchestrator. Calls existing per-source importers as **shared helpers** (refactor extracts from `scripts/import_math_aptitude_datasets.py` as needed). Do **not** bolt this pass onto flags on `import_math_aptitude_datasets.py` (name/scope mismatch; divergent entry smell).

### Steps

```text
1. Load sealed curriculum.json → reverse index (normalized topic_id)
2. Import / refresh from all sources: merge by (source, source_id),
   apply EN drop + manifest (§2), leave empty curated fields open
3. Map · tag · quarantine (§2) — structural note_topic_ids + tags only
4. Note stubs (§3)
5. Seed ReviewCards — one card per question (§3)
6. Print summary + write _meta manifests
```

### Step 2 — Multi-source English import

Sources (existing wiring under `data/math/imports/` + HF where already used): SAT, MathQA, Hendrycks, SAKET, mathgenerator, DeepMind, MathNet, authored packs.

- Apply §2 language rules **at ingest** (drop + `_meta/dropped_non_en` log); mapping step does not re-decide language.
- Answers optional; empty → keep; `answer_format: "open"` when answer empty; MathNet default does **not** require final answer.
- Merge key **`(source, source_id)`**; fill-empty-only on curated fields.
- Default path: **no `--clean-out` wipe**. Destructive wipe remains opt-in on legacy importer only, not the default curriculum pass.
- Authored packs must survive refreshes of generated packs.

### Summary buckets (required)

| Bucket | Meaning |
|--------|---------|
| `kept` | English questions retained in mapped packs |
| `dropped_non_en` | Dropped after language rules (+ manifest with text snippets) |
| `quarantined_unmapped` | Packs (and their question counts) with no curriculum home |
| `packs_multi_topic` | Mapped packs with \|computed MT\*\| > 1 |
| `note_topic_ids_normalized` | Count of invalid (non-curriculum) ids stripped from packs (+ per-pack removed lists in run log) |
| `stubs_created` | New headings/files created |
| `stubs_skipped_nonempty` | Existing non-empty sections left alone |
| `cards_seeded` | ReviewCards created/updated (one per question) |

Artifacts:

- `data/questions/math/_meta/needs_topic.json`
- `data/questions/math/_meta/dropped_non_en.jsonl` (or equivalent)
- Console summary with the buckets above

---

## 5. Architecture sketch

```text
curriculum.json (sealed MT*)
        │
        ▼
math_en_curriculum_pass.py
        │
        ├─► per-source import helpers ──► data/questions/math/**/*.json
        │         (source, source_id) merge · EN drop · empties open
        │
        ├─► map/tag/quarantine ──► _meta/needs_topic.json
        │         additive note_topic_ids + tags
        │
        ├─► note stubs ──► data/notes/math/MT{n}_*.md  (fixed module map)
        │
        └─► content_bank.import_content ──► ReviewCard (1 per question)
```

No changes to Study Loop session model, ADR-001 quiz engine, or tag shape (`MT{n}-Txx`).

---

## 6. Testing / verification

1. Unit: reverse index + normalize; composite key collision (same `source_id`, different `source` → two rows).
2. Unit: language — explicit field wins; below length floor kept; above-floor non-EN dropped and logged.
3. Unit: additive `note_topic_ids` / tags lockstep; fill-empty-only leaves non-empty `answer` intact.
4. Unit: quarantine pack absent from seed set; `packs_multi_topic` counted when \|MT\*\| > 1.
5. Unit: note stub idempotency — fixed module path; heading format parseable by `parse_note_topics`.
6. Integration: dry-run or small fixture pack through orchestrator; `python -m backend.quiz.content_bank --validate`.
7. Manual: spot-check `_meta/dropped_non_en` snippets; open one multi-topic pack and confirm **one** card per question id in DB.

---

## 7. Non-goals reminder (later sprints)

- Fill answers / hints / full notes.
- Split or re-home questions inside `packs_multi_topic`.
- Curriculum edits that mint new `MT*`.
- Code playground (data analysis + data structures).

---

## Decision log (brainstorm)

| Decision | Choice |
|----------|--------|
| Tag scheme | Canonical `MT{n}-Txx` only |
| Approach | A curriculum-first |
| Unmapped | Quarantine (`_meta/needs_topic.json`), no mint, no nearest guess |
| Non-English | Drop (+ manifest); not quarantine |
| `note_topic_ids` vs tags | Both additive to full computed curriculum set |
| Multi-hit packs | Seed + `packs_multi_topic` summary |
| Cards | One per question, full tag set |
| Note files | Fixed `MT{n}` → filename table |
| Heading | `## \`MT1-T07\` — Time & work` |
| Orchestrator | `scripts/math_en_curriculum_pass.py` |
| Merge key | `(source, source_id)` → `id` = `math.{source}.{source_id}` (no `topic_id` in id) |
| Source vocabulary | `sat` · `mathqa` · `hendrycks` · `saket` · `mathgenerator` · `deepmind` · `mathnet` · `authored` |
| Language | Explicit field first; else script heuristic only if len ≥ 24; default-keep below / when unsure |
| Invalid `note_topic_ids` | Strip + log (`note_topic_ids_normalized`); not silent |
