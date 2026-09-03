# Tag importance + Learning-phase recycle — Design

**Date:** 2026-09-04  
**Status:** approved for implementation  
**Related:** ADR-001 · `backend/quiz/srs.py` · `docs/superpowers/specs/2026-09-03-study-loop-design.md`

## Goal

Editable **importance** (1–5) on Study Loop tags so you or Claude can raise the bar for “this topic is mastered” **and** densify FSRS review for high-stakes tags — without a second SRS, without copying importance onto each card, and with an in-session Learning recycle that persists debt on the card.

## Approach

**A — Tag-level lookup store** (chosen). Cards read importance at schedule / progress time. Rejected: bake onto ReviewCard at seed (stale on edit); Daily-Path pass-% only (no density).

---

## 1. Goals, effects, locks

### In scope

- Tag-level store + API + Flash decks / Loop edit UI
- Claude “Suggest importance” writing the same store with provenance
- Mastery bar + FSRS **density** from the table below
- Learning-phase recycle on fail-below-bar (position, escalation cap, persisted debt)
- Low Mastery surface: tags not yet mastered + session from those weak cards
- In-session / Low Mastery queue sort: importance × overdue-ness when truncating
- One `/api/quiz` + one ReviewCard FSRS (ADR-001)

### Out of scope

- Second SRS / parallel mastery engine
- Baking importance into question JSON or ReviewCard payload at seed
- Misconception-targeted retries (needs `solution_steps` enrichment later)
- Force-overwrite of `source: "user"` from Claude

### Verified FSRS field (`backend/quiz/srs.py`)

`ReviewCard.srs_json` ↔ `SrsState`:

| Field | Role |
|-------|------|
| `mastery` | **int**; correct `min(10, +1)`; wrong `max(-2, −2)` |
| `stability` / `difficulty` / `ease` | interval math |
| `consecutive_correct` | streak — **not** the owe-N counter |
| `due_date` / `interval_days` | next review |

Bar compares **`SrsState.mastery`**. Escalation uses a **separate** persisted `owes_corrects`.

### Lock 1 — Multi-tag: max for **scheduling only**

`effective_imp(card) = max(importance(t) for t in card.tags)` (missing tag → default **3**). Used for **interval density** and for **Due/mixed-session Learning entry** when there is no single session tag.

### Lock 2 — Prospective due dates

Changing importance does **not** rewrite existing `due_date`s. Density applies on the next **full** `schedule_after_answer` (the fail that enters Learning, not recycle-corrects).

### Lock 3 — Full bar + density table

| Importance | Bar (`mastery ≥`) | Interval factor |
|------------|-------------------|-----------------|
| 1 | 2 | × 1.25 |
| 2 | 3 | × 1.00 |
| 3 | 4 | × 0.85 |
| 4 | 5 | × 0.70 |
| 5 | 6 | × 0.55 |

Unset tags: **3**.

### Lock 4 — Provenance

Each store row: `{ importance, source: "default" | "user" | "claude", updated_at, note? }`.  
Claude never overwrites `user`. UI shows source.

### Deck-mastered rollup (tag T)

Tag list for progress uses same linkage as Flash decks / tag stitch (`note_topic_ids` + question tags + vocab groups).

Linked cards for T: a card is **cleared for T** iff `mastery ≥ bar(importance(T))` using **T’s own** importance, not max.  
`progress = cleared / total`; `mastered` iff `total > 0 && cleared == total`.

Shared cards: FSRS density uses max; tag X’s progress screen uses X’s bar. Deliberate.

---

## 2. Store, API, scheduling hook, UI

### Store

`data/quiz/tag_importance.json`

```json
{
  "schema_version": 1,
  "default_importance": 3,
  "tags": {
    "MT1-T07": {
      "importance": 5,
      "source": "user",
      "updated_at": "2026-09-04T00:00:00Z",
      "note": "exam week"
    }
  }
}
```

Key = canonical Study Loop tag id. Missing key → behave as default 3; no row until PUT or suggest.

Writes: process **file lock around read-modify-write only** (not LLM). Atomic temp + replace inside that lock. Lock does **not** span network generation.

**Optimistic check (`PUT`):** optional `expected_updated_at`.

- Tag **has a row:** if stored `updated_at` ≠ expected → **409**, no write.
- Tag **has no row** (implicit default): client **omits** `expected_updated_at` or sends `null` to mean “I expect no row.” If a row now exists → **409**. Sending a timestamp for a never-set tag is **409**.

### API (`/api/quiz`, existing auth)

| Method | Path | Behavior |
|--------|------|----------|
| GET | `/importance` | Full map + defaults; optional `?tag=` |
| GET | `/importance/{tag}` | Row + `bar`, `interval_factor`, `progress` `{cleared,total,mastered}` |
| GET | `/importance/low-mastery` | Tags with `progress.mastered == false` (same linkage as Flash decks). Each: `tag_id`, `importance`, `bar`, `cleared`, `total`, `weak_count` (`total - cleared`), `owes_count` (cards with `owes_corrects > 0`). Omit tags with `total == 0`. Sort: `importance` desc, then `weak_count` desc. |
| POST | `/importance/low-mastery/start` | Body `{ tag?: string, count?: number }`. Builds a Learning-phase quiz session from weak cards only: `mastery < bar(T)` or `owes_corrects > 0`, using T’s bar when `tag` is set; if `tag` omitted, union of all low-mastery tags’ weak cards. Queue order §2 “Queue priority”. Recycle rules §3. Same `/api/quiz` start/submit. **Omitted `count` defaults to 15** (Daily Path session size); clamp 1–40. |
| PUT | `/importance/{tag}` | `{ importance: 1..5, note?, expected_updated_at? }` → `source: "user"` |
| POST | `/importance/suggest` | See §4 |

Route note: register `GET /importance/low-mastery` **before** `GET /importance/{tag}` so `low-mastery` is not captured as a tag id.

### Card linkage (progress, Low Mastery, Learning)

Tag list for progress uses same linkage as Flash decks / tag stitch (`note_topic_ids` + question tags + vocab groups).

### Queue priority (in-session and Low Mastery)

When more candidate cards exist than the session `count`, sort **before** truncating:

```text
score = I * (1 + days_overdue)
```

- Tag-scoped session / Low Mastery for **T**: `I = importance(T)` (T’s own row, default 3).
- Mixed Due / omit-`tag` Low Mastery: `I = effective_imp(card)` (max).
- `days_overdue = max(0, floor((now - due_date) / 1 day))`; missing `due_date` → 0.
- If `owes_corrects > 0`, use `days_overdue = max(days_overdue, 1)` (debt is always “due”).
- Tie-break: higher `owes_corrects`, then `item_key`.

This is **in-session / Low Mastery ordering only**. Cross-day density remains Lock 3’s interval factor. Recycle **reinsert** still uses random 3–7 (§3), not this sort.

`owes_corrects` concurrency: local-first **single-user**; each grade is one SQLite commit on that `ReviewCard` row. No extra lock; not a multi-writer store.

### Density hook

After a **full** `schedule_after_answer` (only when `owes_corrects` was 0 going into the grade): multiply `interval_days` by `factor(effective_imp)`, clamp ≥ 1. Any answer while `owes_corrects > 0` is a recycle event (§3 / Persistence) and **does not** run this.

### UI

Flash decks + Loop: 1–5 control, source badge, `cleared/total`. Suggest button → POST suggest.

**Low Mastery** (Study Loop tab or Flash decks section): list from `GET /importance/low-mastery`; **Drill weak** → `POST /importance/low-mastery/start`. Independent of whether any FSRS `due_date` is today — weakness is `mastery < bar(T)` and/or unpaid `owes_corrects`.

---

## 3. Learning-phase scheduler

### Session bar (entry)

- Started from tag **T**: `bar(importance(T))`.
- Due / mixed / no single tag: `bar(effective_imp)`.

**Entry check runs on post-fail mastery** (after −2). If then `mastery < session bar` → set `owes_corrects = 2` (always 2; never 3+). Further fails while owing **reset to 2**.

If post-fail mastery is still ≥ bar → no Learning debt; FSRS lapse only.

### Recycle (fail that created/reset debt)

1. Full grade: `schedule_after_answer(correct=False)` then apply density to that interval / `due_date`.
2. Persist `owes_corrects = 2`.
3. Reinsert in **same session** at bounded-random skip **3–7** remaining cards, **re-rolled each recycle**. Fewer than 3 remaining → append at end.
4. Retry content: **math** → parametric regen (same structure, new numbers, existing SymPy path). Other domains → same stem. No misconception targeting this sprint. Regen variants are **ephemeral**: generated and graded in-session only, never written to `data/questions/math/**`, never assigned `(source, source_id)` / bank `id`. Expected answer lives on the quiz session item payload.

### Recycle-corrects (not full FSRS)

While `owes_corrects > 0` and user is correct:

- `owes_corrects -= 1`
- `mastery = min(10, mastery + 1)` (progress views)
- **Do not** call `schedule_after_answer`
- **Do not** change `due_date` / `interval_days` / stability / difficulty from this event
- If `owes_corrects > 0`: recycle again (3–7 re-roll; math regen)
- If `owes_corrects == 0`: exit Learning recycle; **FSRS due from the fail stands**

Once `owes_corrects > 0`, **debt alone** continues the loop. Mastery returning ≥ bar mid-recovery does **not** exit or orphan debt.

### Persistence

On `ReviewCard.srs_json`: `owes_corrects: int` (0 or missing = none; 1 or 2 = debt). Card state, not session. Due / Low Mastery rebuild: `owes_corrects > 0` keeps the card due even if `due_date` is in the future.

**Any answer to a card with `owes_corrects > 0` is processed as a recycle event per §3, whatever queue served it — Due, Low Mastery, or in-session reinsertion.** Correct: decrement debt, `mastery +1`, no `schedule_after_answer`. Fail: reset `owes_corrects` to 2, no `schedule_after_answer`, reinsert 3–7 / math regen if still in an active session queue. Entry into debt (was 0, post-fail below bar) remains the only path that runs a full FSRS fail grade.

---

## 4. Claude suggest, skips, tests

### Suggest (`POST /importance/suggest`)

Body: `{ tags?: string[], overwrite_claude?: bool }`  
Omit `tags` → current Study Loop tag index.

**Generation (no lock):** call LLM; validate each `{ tag_id, importance, note? }`.

**Write (lock held only here):** apply per-tag rules against **current** file (a PUT that committed during generation is visible):

| Existing `source` | Action |
|-------------------|--------|
| `user` | skip (never overwrite) |
| `claude` | write iff `overwrite_claude` |
| missing / `default` | write `source: "claude"` |

Malformed **content** in a successful LLM response is **partial apply**: valid rows write; invalid rows listed; **not** a 502. Genuine LLM/transport failure → **502**, store **unchanged**.

### Response (detail, not counts-only)

```json
{
  "updated": [{ "tag_id": "MT1-T07", "importance": 5 }],
  "skipped_user": [{ "tag_id": "L5-T03", "reason": "user_locked" }],
  "skipped_claude": [{ "tag_id": "MT1-T01", "reason": "claude_locked" }],
  "dropped_invalid": [
    { "tag_id": "not-a-tag", "reason": "unknown_tag" },
    { "tag_id": "MT1-T02", "reason": "importance_out_of_range", "got": 9 }
  ]
}
```

Counts may be derived from list lengths; lists are required.

### Tests

1. Default 3; PUT → `user`; suggest skips `user`; suggest fills unset; `overwrite_claude` updates `claude` only.
2. PUT 409 on stale `expected_updated_at`; omit/null expected on never-set tag succeeds; timestamp on never-set → 409; PUT while row appeared → 409.
3. Multi-tag: density uses max; tag T progress uses T’s bar.
4. Importance PUT does not change `due_date`.
5. Fail with post-fail mastery below bar → `owes_corrects = 2`; fail while owing resets to 2, never 3.
6. Recycle-correct: `owes_corrects` decrements; `due_date` / `interval_days` / stability **unchanged**; `mastery` may +1.
7. `mastery ≥ bar` with `owes_corrects > 0` still recycles until debt 0.
8. Debt in `srs_json` survives new session / Due rebuild; Due submit with `owes_corrects > 0` is recycle (no interval change).
9. Reinsert offset in 3–7 (or end if queue shorter).
10. Math recycle uses parametric regen (mocked), not identical numbers.
11. **Mixed suggest batch:** valid ids write; invalid land in `dropped_invalid` with `reason`; batch does not abort; 502 only on LLM failure with store untouched.
12. Suggest write vs concurrent PUT: second writer sees committed state; `user` still wins.
13. Low Mastery GET: tags with `mastered == false` and `total > 0`; `weak_count` matches cards below T’s bar; omit mastered tags.
14. Low Mastery start: session contains only weak/owing cards; queue order follows importance × overdue-ness.
15. Ephemeral regen: recycle math item numbers change; no new file under `data/questions/math/**`.

---

## Architecture

```text
tag_importance.json  ← PUT user / suggest claude (lock on write only)
        │
        ├─ progress / Low Mastery: bar(importance(T)) vs card.mastery (tag stitch linkage)
        ├─ queue sort: I × (1 + days_overdue) then Learning recycle 3–7
        ├─ density: factor(max tags) on full FSRS grades only
        └─ Learning: post-fail mastery vs session bar → owes_corrects on srs_json
```

---

## Decision log

| Decision | Choice |
|----------|--------|
| Store | Tag lookup JSON, not per-card copy |
| Effect | Higher bar + denser intervals |
| Multi-tag schedule | max importance |
| Multi-tag progress | tag’s own bar |
| Due on importance edit | prospective |
| Mastery field | `SrsState.mastery` int |
| Recycle-correct | no `schedule_after_answer` |
| Loop continuation | `owes_corrects` once non-zero; bar is entry on post-fail mastery |
| Position | random 3–7, re-roll |
| Escalation | fail → owe 2, cap 2 forever |
| Debt | card `srs_json.owes_corrects`; recycle rules apply in **any** queue |
| Low Mastery start `count` | default 15, clamp 1–40 |
| Suggest lock | write only, not LLM |
| Invalid suggest rows | per-item `dropped_invalid`, partial apply |
| Never-set PUT | omit/`null` `expected_updated_at` |
| Card linkage | Flash decks / tag stitch (`note_topic_ids` + question tags + vocab groups) |
| Low Mastery | GET list + POST start Learning session of weak cards |
| Queue order | importance × overdue-ness when truncating; recycle insert still 3–7 random |
| Math regen | ephemeral in-session; never persist to question bank |
| `owes_corrects` writes | single-user SQLite grade commit; no extra lock |
