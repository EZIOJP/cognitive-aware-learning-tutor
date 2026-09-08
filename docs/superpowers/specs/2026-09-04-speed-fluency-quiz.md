# Design: Speed + correctness fluency (platform quiz)

**Date:** 2026-09-04  
**Status:** Locked (engineering decisions); scope generalized from Math Core → platform  
**Related:** ADR-001 · [Tag importance + Learning](./2026-09-04-tag-importance-learning-design.md) · [Unified quiz completion](./2026-08-17-unified-quiz-completion-design.md) · Math Core consumer draft (`MT1_math_core_drills_DRAFT_v2.md`)

## Goal

Add a **second, additive** fluency track for any quiz item that is **pure recall / fact automaticity**: correct *and* under a per-kind latency threshold — without a second SRS, without gating tag `mastered`, and without overloading Learning-phase `owes_corrects`.

Math Core worksheets (tables, squares, cubes, powers, primes-list probes) are the first **consumer**, not the scope boundary.

## Non-goals

- Folding speed into `mastered`, Daily Bite done, or FSRS due
- Reusing `owes_corrects` for slow-but-correct
- Single-slow-answer punishment
- Speed debt on procedural / multi-step / coding / open-ended items
- A second quiz runner or second scheduler

## Platform rule (locked)

| Decision | Lock |
|----------|------|
| Debt field | Separate `speed_reps_owed` on card SRS metadata — **never** reuse `owes_corrects` |
| Recycle | Reuse Learning recycle machinery (bounded-random **3–7** reinsert; no FSRS `schedule_after_answer` on speed-recycle) |
| Entry trigger | Rolling: **≥ 2 of last 3** correct answers **strictly over** threshold; need a full window of 3; not a single slow |
| Correct-but-slow (outside speed recycle) | Speed-log + maybe open debt only — **does not** update `mastery`, `due_date`, `interval_days`, stability, ease, difficulty, or `mastered` |
| Speed % UI | Additive display beside correctness — **never** a boolean gate on `mastered` |
| Lag | Speed fluency taking longer than correctness mastery is **expected** |

Cross-ref Learning debt: `docs/superpowers/specs/2026-09-04-tag-importance-learning-design.md` (`owes_corrects`, 3–7 recycle, any-queue processing). Speed is a parallel counter with a different entry predicate and pin rule.

## Eligibility (flag-based — all domains)

**Default: ineligible.** Speed fluency applies only when the item (or its tag / content metadata) opts in.

### Preferred flag

| Flag | Meaning |
|------|---------|
| `speed_fluency: true` | This item is pure-recall automaticity; subject to speed debt + threshold registry |
| `recall_fact: true` | Alias / synonym for the same opt-in (implementers may accept either; normalize to one internal boolean) |

Where the flag may live (any one is enough if resolved consistently at submit):

- Content-bank question JSON (`data/questions/**`) — preferred for authored packs
- ReviewCard / session item metadata copied at card upsert
- Tag metadata for homogeneous flash decks (e.g. all cells under a tables tag)

### Domains (examples)

| Domain | Eligible when flagged | Typical kind key |
|--------|----------------------|------------------|
| Math | Tables / squares / cubes / powers raw cells / primes-list probes | `math.tables_cell`, `math.square`, … |
| Vocab | Word ↔ meaning recall | `vocab.word_recall` |
| Lecture (`study`) | Atomic fact cards (single closed recall) | `study.atomic_fact` |

### Explicit non-eligible (even if answer is slow)

Do **not** set `speed_fluency` / do not apply speed debt for:

- Procedural math: factorization, calculation shortcuts, approximation & estimation, divisibility *methods*
- Multi-step lecture problems / synthesis
- Coding / `code` / `coding_mcq` items
- Open-ended reasoning / self-check proofs
- Pattern-*application* procedures (e.g. last-digit cyclicity steps) as distinct from raw memorized table cells

Hardcoding topic IDs (`MT1-T16`…`T19`) in the engine is **forbidden**. Topic lists belong in content flags (Math Core consumer doc suggests which MT1 items to flag).

## Pinned instance (identical-fact retry)

Speed trains a **specific association**. While speed debt is active (and preferably for the rolling latency window):

1. Re-serve the **exact same fact** (same multiplicands, same `n`, same vocab prompt, same lecture atomic).
2. **`speed_fluency` implies pinned instance** for the debt lifetime.
3. Generator-backed items marked speed-eligible (rare): either **pin** the generated instance for the debt lifetime, or **disallow** `speed_fluency` on regenerating items. Prefer pin.
4. Correctness recycle may still regen parametric math **when not on the speed path** and when existing Learning rules allow — do not collapse the two paths.

## Separate debt type

| Field | Role |
|-------|------|
| `owes_corrects` | Correctness debt — post-fail mastery &lt; bar. Unchanged. |
| `speed_reps_owed` | Speed debt — rolling slow-correct trigger. Default / missing = `0`. |
| `speed_recent_correct_ms` | `int[]` last **3** correct-only latencies for that fact. Wrong answers do not append. |

Persist on `ReviewCard.srs_json` (extend `SrsState` / `srs_from_metadata` / `srs_to_metadata`) — same card lifetime as `owes_corrects` (survives session end).

If both debts are non-zero: process **`owes_corrects` first**, then `speed_reps_owed`.

## Entry / exit / recycle

### Entry (correct answer, eligible, not already owing speed)

1. `response_ms = submit_ts − render_ts`
2. Resolve registry key → threshold ms
3. Append to `speed_recent_correct_ms` (cap 3)
4. If window length &lt; 3 → no debt
5. If ≥2 of last 3 are **&gt;** threshold and `speed_reps_owed == 0` → set `speed_reps_owed = 2` (never 3+ on entry)

### While `speed_reps_owed > 0`

Reuse Learning recycle shape:

- Reinsert **3–7** ahead (same re-roll / append rules)
- **No** `schedule_after_answer` from the speed path
- Correct **and** ≤ threshold → `speed_reps_owed -= 1`; reinsert if still &gt; 0
- Correct but still slow → log window; **do not** decrement; reinsert
- Wrong → leave `speed_reps_owed` unchanged for the speed counter; still run normal correctness path (may set/reset `owes_corrects`)

Speed-recycle attempts must **not** bump mastery / due / interval from the speed branch (correctness branch may still apply when processing `owes_corrects`).

## No pressure on mastery / `mastered`

| Event | mastery / FSRS | `mastered` | speed |
|-------|----------------|------------|-------|
| Correct under threshold, no debts | normal full grade | may clear via bar | log; may clear speed debt |
| Correct over threshold, no speed debt yet | normal full grade if not in recycle | unchanged by speed | log; maybe open debt |
| Speed-recycle (any RT) | **no** change from speed path | **no** | debt ± / reinsert |
| Wrong | existing `owes_corrects` rules | per those rules | no window append |

```text
correctness: mastered · speed: 62% of facts under threshold
```

`mastered` remains correctness-only (`mastery ≥ bar(T)` + existing tag rollup). Speed % never gates it.

## Threshold registry (per domain/kind)

Not one Math Core table and not one global ms. Named constants keyed by kind:

| Registry key | Threshold (ms) | Notes / first consumer |
|--------------|----------------:|------------------------|
| `math.tables_cell` | 2500 | `MT1-T19` random `n × m` |
| `math.square` | 3000 | `MT1-T16` raw `n²` |
| `math.cube` | 4000 | `MT1-T17` raw `n³` |
| `math.power_raw` | 3500 | `MT1-T18` raw bases 2/3/5/7 |
| `math.prime_list` | 2500 | `MT1-T21` list probes only |
| `vocab.word_recall` | TBD (suggest 4000) | Meaning ↔ word flash |
| `study.atomic_fact` | TBD (suggest 5000) | Single closed lecture fact |

Tune later. Do **not** reuse FSRS soft `elapsed_ms > 45_000` stability nudge as a fluency threshold.

Item metadata should carry `speed_kind` (registry key) when flagged, or resolve from content pack defaults.

## Completion percentage

For flagged facts `F` in a deck/tag set:

```text
speed_pct = 100 * |{ f ∈ F : fluent(f) }| / |F|
```

`fluent(f)`: ≥3 correct samples and ≥2 of last 3 **≤** threshold(f). Facts with `speed_reps_owed > 0` are not fluent until debt clears **and** the window satisfies fluent.

Display-only: does not gate Daily Bite, `mastered`, or FSRS due.

## Code landing (design only — not implemented by this spec)

| Layer | Where |
|-------|--------|
| State fields | `backend/quiz/srs.py` — `SrsState.speed_reps_owed`, `speed_recent_correct_ms`; serialize in `srs_to_metadata` / `srs_from_metadata` |
| Submit branch | `backend/quiz/handler.py` (and importance recycle path in `backend/quiz/importance.py`) — after correct/wrong resolve: if `speed_fluency` and debts ordered (`owes_corrects` then speed) |
| Thresholds | New small module e.g. `backend/quiz/speed_fluency.py` — registry + fluent/debt helpers |
| Content flag | `docs/QUESTION_CONTENT_FORMAT.md` + `content_schemas.py` / content-bank item builders — optional `speed_fluency`, `speed_kind` |
| Frontend timing | Question show → submit: ensure `response_ms` / `time_taken_ms` from render timestamp in GlobalQuizRunner / quiz UI |
| UI | Additive speed % beside mastered chip; calm “again for speed” copy; optional badge while `speed_reps_owed > 0`; never block day-done (same spirit as lingering `owes_corrects`) |

## Interaction summary

```text
wrong → correctness path → may set owes_corrects
correct + rolling slow + speed_fluency → may set speed_reps_owed (never owes_corrects)
both > 0 → owes_corrects first; then speed
speed recycle → pinned identical fact; no FSRS from speed path; no mastery bump from speed path
correctness recycle → existing rules (math regen where already specified)
```

## Math Core consumer

Author flags on pure-recall cells only. Suggested mapping (content, not engine hardcode): see Downloads draft **Speed + correctness fluency** section in `MT1_math_core_drills_DRAFT_v2.md` (v2.2+). Leave factorization / shortcuts / estimation / divisibility methods / cyclicity procedure **unflagged**.

## Expected timeline

Speed automaticity lagging correctness mastery is correct product behavior. Do not tighten thresholds or fold speed into `mastered` to “fix” the lag.
