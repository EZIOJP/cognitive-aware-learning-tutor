# Prod P5 — Native unlock accounting, classification and scoring (design)

**Date:** 2026-09-08
**Status:** P5a implemented and verified 2026-09-11; P5b/P5c not started
**Owner decision:** unlock accounting belongs in C++, end to end
**Supersedes for this area:** the Python ownership described in [docs/BLOCKING_RULES.md](../../BLOCKING_RULES.md) "Goals, earning and unlocks"
**Related:** [product lock](2026-09-07-calt-productivity-cpp-product-design.md) · [Phase 2 gateway](2026-09-08-calt-productivity-phase2-gateway-design.md) · [Focus standalone](2026-09-11-calt-focus-standalone-productivity-design.md) · [BLOCKING_RULES](../../BLOCKING_RULES.md)

---

## 1. Why

`AGENTS.md` already locks this:

> **PRODUCTIVITY RULE (locked 2026-09-07):** SoftLand decide, day-pass/free/incubation
> accounting, and productivity tracking runtime belong to the C++ Productivity
> product — not the study webapp.

Today they do not. Reward days, day passes, earned minutes, incubation limits and
every "is the day unlocked" decision live in Python and need `:8000` up. Phase 2
moved the *policy* and the *plumbing* to C++ and stopped there.

The gap is not theoretical. Two proofs found on 2026-09-08:

1. **A day pass unlocks no website at all.** `request_day_pass`
   (`backend/bible/store.py:611`) writes only the Bible day file, and
   `SoftlandGetMode` never reads `runtime.day_pass`. Since Prod P4 turned off the
   Gate's HTTP fallback, the Python-side `day_unlimited` no longer reaches the
   browser, so burning one of your two weekly passes leaves YouTube blocked.
   Reward days work only because someone hand-wired
   `_sync_reward_day_to_softland_policy`; nobody wired the pass.
2. **`softland.set_day_pass` is a command nobody reads.** The op exists
   (`cmd_gateway.cpp:408`), the field exists (`productivity_store.cpp:564`), the
   spec documents it — and the decide path ignores it.

Both are symptoms of split ownership: the mechanism is native, the rules are
Python, and nothing guarantees they meet.

## 2. The one-scorer rule (condition of doing full P5)

Choosing full P5 over the minimal fix is right **only if it is a move, not a
copy**. Python already contains *two* disagreeing "productive minutes"
implementations:

| | Unlock path (`distraction_gate`) | `goal_met` chip (`goals_alerts`) |
|---|---|---|
| Threshold | policy `threshold` | hardcoded 60 |
| Overlaps | merged | bucket sums |
| Sleep | subtracted | not subtracted |
| Sources | all | 3 only |
| Bible chapter | **required** | ignored |

A third implementation in C++ would be worse than one in the wrong language.

> **P5 RULE:** when P5 is done, exactly one process computes productive time and
> unlock state — `calt_enforcer`. Python and the UI *read* that answer. Any Python
> code that still computes it is deleted, not left "for compatibility".

## 3. Non-goals

- Moving study content. Chapters, notes, the daily bite and plan authoring stay
  in Python; they emit **events**, they never decide unlock.
- Moving wearable ingest. Sleep comes from health dumps Python already imports;
  P5 only changes how the enforcer *consumes* it.
- Re-litigating Arm, kills, or the Gate path. Done in N1–N3 / Z0–Z4 / Prod P3–P4.
- New UI. Figma's Settings overhaul consumes this; it is not blocked by it.

## 4. What moves, what stays

| Concern | Today | After P5 | Why |
|---|---|---|---|
| Day-pass quota (2/Mon–Sun week), `PASS` confirm | `bible/store.py` JSON | enforcer + `productivity_*` | pure accounting |
| Day-pass grant → free window | **broken** | enforcer, one mechanism | fixes gap 1 |
| Reward credit ledger (qualified/used dates, 4-per-credit) | `reward_days.py` JSON | enforcer + `productivity_*` | pure accounting |
| Earn rates 15/10/30 + 60/day cap | `break_reward.py` | enforcer | pure accounting |
| Earn *triggers* (Bible done, plan confirmed, goal hit) | Python decides + credits | Study **emits event**, enforcer credits | study content in, accounting out |
| Incubation duration / 1-per-hour / streak trigger | `break_reward.py` | enforcer (tick already there) | tracking runtime |
| Classification (15 app + 76 domain rules) | Python, backfilled after insert | rules-as-data, enforcer classifies at insert | one rule set |
| Category scores + threshold + overrides | Python + DB table | enforcer reads same table + policy mirror | one scorer |
| Productive minutes + sleep subtraction | `distraction_gate` | enforcer, published rollup | one scorer |
| "Is the day unlocked" | `distraction_gate.py:784` | enforcer, published | the whole point |
| Chapter ticked / plan confirmed / bite done | Python (correct) | Python → gateway event | genuinely study |
| Sleep windows | `WearableDaily` payload parsed in Python | Python publishes a per-day mirror; enforcer subtracts | keeps JSON parsing out of C++ |
| Goal display, streak UI, history | Python computes | Python reads native rollup | one scorer |

## 5. Sub-phases

Three subsystems, each shippable and verifiable alone. Do them in order.

### P5a — Native unlock accounting (no scoring)

**Status: Done (2026-09-11).**

Moves every quota and currency that needs no productive-time maths.

- `productivity_day_passes`, `productivity_reward_credits` tables + one-time
  import of `data/bible/day_passes_*.json` and `reward_days_*.json`.
- Gateway ops: `day.grant_pass` (enforces the 2/week quota and the `PASS`
  phrase natively), `day.mark_event` (`chapter_done` | `plan_confirmed` |
  `bite_done` | `daily_goal`), `reward.claim` (enforces `REWARD`), `day.status`,
  plus bridge ops `reward.mark_qualified` / `reward.grant_credits` until P5c.
- Earn rates and the 60/day cap enforced in the enforcer on `day.mark_event`.
- Incubation duration and the 1-per-hour limit enforced on
  `softland.set_incubation`.
- **Day-pass grant writes `free_until` (the single free-window mechanism) plus
  `runtime.day_pass` as audit.** SoftLand decide already honours `free_until`.
- Python's `request_day_pass` / `claim_reward_day` are thin gateway callers;
  quota and streak JSON code deleted.

**Verified (2026-09-11, console enforcer, Study `:8000` not required):**

```text
smoke_p5a.ps1 -Mutate
  → P5a smoke: all checks passed

day.grant_pass {"confirm":"PASS"}
  → ok:true, free_until:2026-09-11T23:59:59

msg_host_cmd get_mode https://youtube.com
  → action:allow mode:free reason:free_window until:2026-09-11T23:59:59
  (bug fix — previously blocked)

2 synthetic passes this week + grant
  → error:pass_quota_exhausted

day.mark_event chapter_done → credited_seconds:900
  repeat → event_already_recorded
  plan_confirmed → credited_seconds:600

softland.set_incubation ×2 → second: incubation_rate_limited

Import from reward_days_1.json
  → qualified=8 used=5 granted=3 (matches JSON); no day_passes_*.json present

pytest tests/test_bible_day_pass.py tests/test_reward_days.py
       tests/test_break_reward.py tests/test_morning_rewards.py
  → 18 passed
```

**Exit:** with `:8000` stopped, `day.grant_pass` unlocks watch sites through the
real Gate path, refuses a third pass in one week, and `reward.claim` refuses
without available credits. Existing pass/credit history survives the import.

### P5b — Native classification and scoring

- **Rules as data.** A generator script writes `data/behavior/classify_rules.json`
  from the existing `_APP_RULES` (15) and `_DOMAIN_RULES` (76) plus
  `category_scores` and `DEFAULT_SCORE`/`PRODUCTIVE_THRESHOLD`. The enforcer
  reads that file. The Python literals stay the authoring source; neither side
  hardcodes a second copy.
- `session_db.cpp` classifies at insert (`category`, `category_source='native-rules'`)
  instead of writing `NULL`, which retires
  `backfill_native_session_categories`.
- Python publishes `data/behavior/sleep_windows.json` for the local day from
  `WearableDaily`; the enforcer subtracts those intervals.
- Enforcer computes merged productive seconds per local day and publishes
  `data/behavior/day_rollup.json` + a `productivity_day_rollup` row.

**Exit:** native rollup matches Python's `distraction_gate` figure for the same
day within 60s, on three sample days, with the same policy.

### P5c — Native qualification, Python as reader

- Enforcer decides `goal_met` and `day_unlocked` from its own rollup plus the
  chapter event, records the qualifying day at local midnight, and grants reward
  credits on the 4th.
- `distraction_gate` and `goals_alerts` stop computing and start reading the
  rollup. The duplicate scorer in `goals_alerts` is **deleted** per §2.
- `softland_policy.goals.goal_met` finally has a writer, or is removed.

**Exit:** a full day earns its streak credit with `:8000` stopped the whole day,
and the `goal_met` chip and the unlock state can no longer disagree.

## 6. Command surface additions

Same framing as Phase 2: named pipe `\\.\pipe\calt_enforcer_cmd`, enforcer is the
only mutator.

| Op | Payload | Enforces |
|---|---|---|
| `day.grant_pass` | `{confirm}` | `PASS`, 2/Mon–Sun week, sets `free_until` + `day_pass` |
| `day.mark_event` | `{event, at?}` | once-per-day per event, earn rate, 60/day cap |
| `day.status` | — | reports pass quota, credits, earned balance, rollup, unlock |
| `reward.claim` | `{confirm}` | `REWARD`, `available > 0`, refuses if already unlocked |
| `reward.status` | — | earned / granted / spent / available / days-to-next |

`softland.set_day_pass` is kept as a low-level escape hatch but is no longer how
a pass is granted.

## 7. Risks

| Risk | Mitigation |
|---|---|
| Two writers during the transition | `ProductivityImportIfStale` already reconciles Python JSON writes; P5a deletes the Python quota code in the same task that adds the native one |
| Classification drift between languages | rules-as-data (§P5b); C++ never hardcodes rules |
| Sleep data unavailable | absent mirror = subtract nothing (today's behaviour when wearables are missing) |
| Import loses history | import is idempotent and reads the existing JSON; verify counts before deleting the files, keep them as backups |
| Scope creep into tracking | P5b touches classification and scoring only; browser-path tracking stays Prod P6 |

## 8. Exit criteria for P5 as a whole

1. `:8000` stopped for a whole day: tracking, scoring, unlock, streak credit and
   pass/reward spending all still work.
2. Exactly one implementation of productive time exists in the repo.
3. A day pass unlocks watch sites through the native Gate path.
4. `docs/BLOCKING_RULES.md` §"Goals, earning and unlocks" is rewritten to say
   C++ owns it, and its "needs `:8000`" caveats are deleted.
