# Daily bite Study Loop — Design

**Date:** 2026-09-04  
**Status:** approved for implementation  
**Related:** ADR-001 · [Study Loop](./2026-09-03-study-loop-design.md) · [Daily Path MT](./2026-09-02-daily-path-math-mt-design.md) · [Tag importance + Learning](./2026-09-04-tag-importance-learning-design.md)

## Goal

After morning plan confirm, land on **today’s Study Loop bite**: two sequential tags (read → questions), chosen by the same importance × overdue score as Low Mastery truncation — without a second SRS, without inventing a parallel curriculum pacer, and with interleaved mode **C** turning on only when every tag in that day’s list has a stored non-stub note.

Daily Path “assigned MT/L tags” was **intent only**. This spec is that assignment mechanism.

---

## Approach

**B now, C as content-gated upgrade** (chosen). Rejected: one tag per day only; weekday/weekend C; C immediately over stub notes.

---

## 1. Locks

### In scope

- Freeze today’s N tags per `user_id` + local calendar day
- Sequential B: existing per-tag Study Loop gate (read → mark-read → start-practice)
- Auto C when **all** tags in that frozen list are non-stub
- Morning `next`: `bible → plan → study → open`
- Empty / in-progress / done surfaces (no fake quiz)
- Stub flag store (not body-string match)
- One `/api/quiz` + one ReviewCard FSRS (ADR-001)

### Out of scope

- Balancing question *volume* across the N tags (known imbalance: N is tag count, not item count; T1×3 vs T2×40 is accepted)
- Second selection formula besides importance × overdue
- Using `curriculum.json` as a ranking/pacer (it stays a catalog / Review Hub dropdown)
- Auto-filling tag importance for all L*/MT* (existing PUT / Suggest)
- Forcing `owes_corrects` to 0 before the day can complete
- Weekday/weekend pedagogy toggle

### Mode

| Mode | Shape |
|------|--------|
| **B** | N tags in freeze order. For each: read card(s) → mark-read → that tag’s practice session. Next tag starts only after this tag’s gated set is **attempted**. |
| **C** | Same N tags as one bundle. Mark **all** N notes read, then **one** mixed `/api/quiz` session. Learning entry bar = `bar(effective_imp)` (max on the card), same mixed-session rule as importance spec §1 / §3. |

A day is **all B or all C**. No half-bundle C.

**N = 2.** If fewer than 2 eligible candidates, take all of them (0 or 1).

---

## 2. Selection (today’s bite)

### Candidates

A Study Loop tag is eligible iff **all** of:

1. **Not mastered** — importance progress for tag T: `mastered == false`. (`mastered` remains `total > 0 && cleared == total` using **T’s own bar** and ReviewCard linkage.)
2. **Has practice inventory** — `practice_count > 0`.

`practice_count` = items the existing Study Loop practice route can actually start: content-bank / question-CRUD rows stitched to T (`note_topic_ids` or question tags) **plus** live mathgenerator recipes for MT tags **plus** vocab words when T is `vocab.group.N`. This is the Flash decks / `start-practice` inventory, **not** `GET /importance/{tag}` `progress.total`.

**Why not reuse Low Mastery `total`:** that `total` is **ReviewCard** count. `total == 0` there correctly means “nothing to drill for weakness.” Reusing it here would exclude **never-practiced** tags that already have a question bank — the opposite of Daily Path. The **intent** matches Low Mastery (“omit tags you cannot quiz”); the **denominator** is practice inventory. Tags with a stub heading and **zero mapped questions and no generator** have `practice_count == 0` and **must not** be T1/T2 (avoids read-then-no-quiz).

Never-practiced + `practice_count > 0`: `progress.total == 0` ⇒ `mastered == false` ⇒ **eligible**.

### Score

Among candidates, same formula as Low Mastery queue truncation ([importance spec](./2026-09-04-tag-importance-learning-design.md) §2):

```text
score = I * (1 + days_overdue)
```

- `I` = `importance(T)` (T’s own row, default 3).
- `days_overdue` from that tag’s linked ReviewCards: use the **max** `days_overdue` among those cards (missing `due_date` → 0; `owes_corrects > 0` → `max(days_overdue, 1)`). No ReviewCards → 0. New high-importance tags still rank by **I**.
- Tie-break: higher `owes_count` for the tag, then `tag_id`.

Take top **N** (2). **Freeze** `{ user_id, local_date → { tags[], mode } }` at first compute that day. Later grades do **not** reshuffle. No “rebuild today” in this sprint.

`mode` is computed at freeze time from stub flags (below). If a note is edited from stub → real **the same day**, the freeze keeps B; C starts the **next** day’s freeze. (No mid-day mode flip.)

`curriculum.json` is **not** consulted for ranking.

---

## 3. Stub flag (C eligibility)

Do **not** detect stubs by matching body text (`TODO: fill notes` or similar). Humans edit that string.

Store `data/quiz/topic_stub_flags.json` (process file lock on write, atomic replace — same pattern as `tag_importance.json`):

```json
{
  "schema_version": 1,
  "tags": {
    "MT1-T07": { "stub": true, "updated_at": "2026-09-04T00:00:00Z" }
  }
}
```

Missing key → treat as **stub true** only if the note section was created by `ensure_note_stubs` in this sprint’s backfill; otherwise missing key → **stub false** (legacy filled lecture notes). **Backfill on first load:** for each MT/L topic in the note index, set `stub: true` iff the section body is empty or exactly the generator placeholder **once**, then never re-derive from body.

**Writes:**

| Event | Flag |
|-------|------|
| `ensure_note_stubs` creates a new heading | `stub: true` |
| `ensure_note_stubs` skips nonempty existing section | do **not** overwrite an existing `stub: false` |
| First **real edit** of that section (Study Loop read-card PATCH / library write-back that changes body) | `stub: false` |
| Claude/user note enrichment that writes real prose | `stub: false` |

C for the frozen day iff **every** tag in `tags[]` has `stub === false`. Else B.

---

## 4. Done, debt, and day states

**Gated set:** items actually served in that tag’s (or C’s mixed) practice session, capped by existing start-practice `count` (default **15**, same as Low Mastery start / importance “Daily Path session size”).

**Attempted:** that item received at least one answer event in that session (`times_asked` increment / session attempt row). Correctness and `owes_corrects` do **not** matter.

**Bite done (tag, B):** mark-read complete **and** every item in that tag’s gated set attempted once.

**Bite done (day):**

- **B:** both (or all N) tags bite-done.
- **C:** all N mark-read **and** every item in the single mixed gated set attempted once.

Lingering `owes_corrects` is **allowed**. Debt is not a done-gate; it surfaces in Due / Low Mastery per the importance spec (any-queue recycle). User may leave mid-recycle; day can still complete.

**In progress:** freeze exists, day not done, at least one step unfinished (unread, or read but gated set incomplete). Resume the first unfinished step; do not recompute tags.

| State | UI | After plan confirm |
|--------|----|--------------------|
| No freeze yet, **zero candidates** | Empty loop: distinguish “no tags/questions indexed” vs “all eligible tags mastered”. Link Due if `due_count > 0`. Flash decks ungated. No quiz start. | Soft-land empty Study Loop (`/review` loop tab). `next` → `open` (nothing to force). Bible/profile allowed. |
| Freeze with 1–2 tags, **not started** | “Today: T1 then T2” + B or C badge. Start T1 read (B) or combined read list (C). | Soft-land that screen. `next` = `study` until day done. |
| **In progress** | Continue first unfinished step. | Same URL; resume. |
| **Day done** | “Path done.” CTA Due / Low Mastery. No new forced N. | Soft-land Due (`/review?tab=due`) or done banner. `next` = `open`. |

Escape hatches (ungated): Due, Flash decks, Create deck — unchanged from Study Loop spec.

Morning gate: extend `next` with `"study"` between `plan` and `open`. Confirm plan → `study` if candidates or an unfinished freeze exist; else `open`. Completing the day’s bite → `open`. Do not trap on empty. `allow_paths` includes `/review` (and existing bible/profile) while `next === study`.

`morning.daily_practice` Due nudge **stays**; it is not topic assignment.

---

## 5. API / persistence

| Method | Path | Behavior |
|--------|------|----------|
| GET | `/api/quiz/study-loop/today` | Freeze if needed; return `{ day, tags, mode, state, current_step, stub_flags }`. `state`: `empty` \| `ready` \| `in_progress` \| `done`. |
| POST | `/api/quiz/study-loop/today/start` | Idempotent: return current freeze; create B loop session for current tag or C bundle session. |

Practice/mark-read: existing Study Loop session routes. C start-practice: `read_completed` only when **all** bundle tags marked read; then `domain=mixed` with items from all tags, `count` default 15, queue sort = importance spec mixed (max I × overdue). Learning recycle unchanged.

Persist freeze: SQLite keyed by `user_id` + `day` (progress is per-user; not the global importance JSON). Stub flags: file store above (content, not per-user).

---

## 6. Tests

1. Candidate with `practice_count == 0` never appears in today’s tags even if `mastered == false`.
2. Never-practiced tag with bank questions (`progress.total == 0`, `practice_count > 0`) can be selected.
3. Freeze stable after a grade that would change scores.
4. New stub from `ensure_note_stubs` writes `stub: true`; write-back sets `stub: false`; leftover `TODO: fill notes` in a `stub: false` body does **not** force B.
5. Day with one stub tag in the freeze stays B even if the other is filled.
6. Day with both `stub: false` freezes as C.
7. Day done with `owes_corrects > 0` on a served card still `state=done`; card remains Due.
8. Empty candidates → `state=empty`, start rejected, morning `next` not stuck on `study`.
9. Plan confirm with a freeze in progress → `next=study` and `/review` allowed.

---

## Architecture

```text
topic_stub_flags.json  ← stub true at stub-create; false on first real edit
tag_importance.json    ← I for score
ReviewCards            ← mastered / days_overdue / owes (not practice_count)
question stitch        ← practice_count
        │
        ▼
GET today freeze top-2  → B sequential loop  or  C combined read + mixed quiz
        │
        ▼
morning.next = study until attempted-once gated sets done → open / Due
```

---

## Decision log

| Decision | Choice |
|----------|--------|
| Pedagogy | B now; C iff all frozen tags `stub === false` |
| N | 2 tags, not question-volume balanced |
| Assignment | Score I × (1 + days_overdue); freeze per user/day |
| Empty-quiz guard | `practice_count > 0` (inventory), not ReviewCard `total` |
| Stub | Stored boolean, not body parse after backfill |
| Done | Attempted once per gated item; debt may remain |
| C Learning bar | `bar(effective_imp)` max |
| curriculum.json | Catalog only |
| Post-plan | `next=study` then Due/`open` when done or empty |
