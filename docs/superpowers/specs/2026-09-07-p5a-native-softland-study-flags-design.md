# P5a — Native SoftLand decide + study flags

> **SUPERSEDED (2026-09-07 evening)** by  
> [2026-09-07-calt-productivity-cpp-product-design.md](./2026-09-07-calt-productivity-cpp-product-design.md)  
> and [softland-state-model](./2026-09-07-calt-productivity-softland-state-model.md).  
> Product lock: SoftLand + day-pass/free/incubation are **first-class C++ Productivity state**, not “Python publishes study flags.” Optional study *events* may still write into the productivity store later. Keep this file as historical Option A sketch only.

**Date:** 2026-09-07  
**Status:** **SUPERSEDED** — historical Option A sketch  
**Authoritative now:** [2026-09-07-calt-productivity-cpp-product-design.md](./2026-09-07-calt-productivity-cpp-product-design.md)  
**Parent map:** [2026-09-07-one-engine-map.md](./2026-09-07-one-engine-map.md)

## Goal

| Owns | Role |
|------|------|
| **C++** (`calt_msg_host` and/or `calt_enforcer`) | SoftLand **site allow/block decision** + hard-block **process kills** |
| **Python** | Webapp only for product UI (notes, Study Loop, planner, GRE, …) + **writer** of study facts into shared state |

Gate must stop depending on a full live `distraction_gate` HTTP round-trip for every SoftLand decision. Python may still *compute and publish* study flags; native *decides* sites.

**Not in scope for P5a:** Porting all of `distraction_gate.py` into C++ (that is closer to P5b / weeks of work).

## Non-goals

- Moving notes / quiz / GRE / planner editing into C++  
- Putting SoftLand site logic back into Python kills  
- Expanding Qt / `calt_desktop` UI  
- Jumping to Option B (zero Python for SoftLand) before P5a works  
- Changing DESKTOP TRACKER RULE for kills (still zero Python at kill time)

---

## Architecture (P5a)

```text
Edge CALT Gate
    → Native Messaging → calt_msg_host
         → read softland_policy.json (allow/block lists, mode defaults)
         → read study_flags.json (or SQLite row) written by Python webapp
         → decide: allow | softland_block | interstitial
         → (optional) if flags missing/stale: fail-closed SoftLand OR last-known

calt_enforcer (unchanged role)
    → enforcer_policy.json → process kills
    → may share lock/anti-tamper with SoftLand “day locked” later; not required in P5a

Python FastAPI :8000
    → serves React webapp + study APIs
    → on Bible / plan confirm / goal / day-pass / SoftLand toggle:
         write study_flags.json (and keep SQLite as source of truth for the app)
```

### Fail behavior when Python is down

| Flags file | Behavior (P5a default) |
|------------|-------------------------|
| Present + fresh (`updated_at` within TTL, e.g. 24h) | Native decides from flags + local SoftLand lists |
| Missing or stale | **Fail closed** for distracting categories (SoftLand study-only), unless `softland_enabled` false in policy file |
| Kill path | Unaffected — enforcer never needs uvicorn |

Owner may later choose “last-known open” — do not default to fail-open.

---

## Shared state: `study_flags.json`

**Path:** `data/behavior/study_flags.json`  
**Writer:** Python only (webapp / gate hooks after study events).  
**Readers:** `calt_msg_host` (primary); optionally `calt_enforcer` for future incubation alignment.  
**Format:** UTF-8 JSON, atomic write (temp + rename).

### Schema (v1)

```json
{
  "schema_version": 1,
  "day": "2026-09-07",
  "updated_at_unix": 1757232000,
  "softland_enabled": true,
  "bible_done": false,
  "plan_confirmed": false,
  "goal_met": false,
  "study_loop_required": false,
  "study_loop_done": false,
  "day_pass_active": false,
  "reward_day_active": false,
  "free_override_until_unix": 0,
  "earned_free_until_unix": 0,
  "incubation_active": false,
  "browser_daytime_default": "study",
  "browser_free_after_hhmm": "21:00",
  "mode_hint": "study",
  "note": ""
}
```

| Field | Meaning |
|-------|---------|
| `day` | Local calendar day these flags apply to; native ignores stale day |
| `softland_enabled` | SoftLand commitment on (legacy DB: `hard_block_enabled`) — **not** OS armed |
| `bible_done` / `plan_confirmed` / `goal_met` | Morning / SoftLand unlock inputs |
| `study_loop_*` | Optional SoftLand gate for daily path |
| `day_pass_active` / `reward_day_active` | Temporary SoftLand relief until midnight |
| `*_until_unix` | Timed free SoftLand windows (PIN free / spend earned) |
| `incubation_active` | Stricter SoftLand / align with enforcer incubation bit |
| `mode_hint` | Optional last Python-computed label for UI; **native must recompute** from flags + clock, not trust blindly |

### SoftLand lists (separate file)

**Path:** `data/behavior/softland_policy.json` (v1)

```json
{
  "schema_version": 1,
  "updated_at_unix": 0,
  "block_domains": ["youtube.com", "reddit.com"],
  "allow_domains": ["localhost", "127.0.0.1"],
  "block_categories_note": "optional; v1 can be domain lists only"
}
```

Python writes this when productivity SoftLand / Gate domain policy changes. Native matches host against lists (suffix rules, same spirit as Gate today — detail in implementation plan).

---

## Native decision (pseudocode)

```text
function softland_decision(url, now):
  flags = read study_flags.json
  lists = read softland_policy.json
  if not flags.softland_enabled:
    return ALLOW
  if flags.day != today_local():
    return FAIL_CLOSED_STUDY  # or treat as softland_enabled with no unlocks
  if flags.day_pass_active or flags.reward_day_active:
    return ALLOW_WITH_ADULT_FILTER  # product rule: tracking may stay on
  if flags.free_override_until_unix > now or flags.earned_free_until_unix > now:
    return ALLOW
  if after(flags.browser_free_after_hhmm) and morning_gates_satisfied(flags):
    return ALLOW
  if not flags.bible_done or not flags.plan_confirmed:
    return BLOCK_OR_INTERSTITIAL  # morning SoftLand
  if flags.study_loop_required and not flags.study_loop_done:
    return BLOCK_DISTRACTION_ONLY
  if flags.goal_met and flags.bible_done:
    return ALLOW  # game-bank unlock style — refine to match current SoftLand
  if host_matches(lists.block_domains):
    return BLOCK
  return ALLOW_STUDY_DEFAULT
```

Exact morning/game-bank parity with today’s `distraction_gate` must be checked against current Python behavior in the **implementation plan** (table of cases). P5a may ship a **reduced** rule set if documented; full parity can be P5a.1.

---

## Gate contract change

| Phase | Gate talks to |
|-------|----------------|
| Today | HTTP `:8000` distraction_gate / SoftLand mode |
| P4 | Native host; host **relays** to Python (prove messaging) |
| **P5a** | Native host; host **decides** from flags + lists (Python optional for flag refresh only) |
| P5b | Same, but flags updated only via file/DB writers; no live SoftLand HTTP at all |

Extension keeps one messaging API: e.g. `{ "cmd": "softland_check", "url": "..." }` → `{ "action": "allow"|"block"|"interstitial", "reason": "..." }`.

During P4→P5a transition: feature flag `SOFTLAND_NATIVE=1` or host capability bit so rollback is one switch back to HTTP.

---

## Python writer hooks (minimal)

Publish `study_flags.json` whenever any of these change (same places SoftLand mode would refresh today):

- Bible chapter complete / day-pass / reward day  
- Plan confirm / morning gate advance  
- Daily goal minutes met  
- Study Loop gate toggle / path complete  
- SoftLand on/off (`softland_enabled`)  
- Free override / spend earned  
- Incubation start/end  

Implementation: one function `publish_study_flags(db, user_id)` called from existing gate/policy paths — **do not** scatter ad-hoc JSON writes.

Keep SQLite as app source of truth; the file is a **projection** for native.

---

## Relation to hard block

| SoftLand (native decide) | Hard block (enforcer) |
|--------------------------|------------------------|
| Domains / tabs in Edge via Gate + host | Process kills via `enforcer_policy.json` |
| `softland_enabled` | `hard_block_armed` |
| Must never set `hard_block_armed` from SoftLand publish | Focus / Settings `#focus` owns Arm |

Callout stays: SoftLand ON does not kill Steam; Arm does not SoftLand sites.

---

## Sequence (do not skip)

1. **P1** — Broad browser list + anti-tamper while locked (+ Admin service once, owner-run).  
2. **P4** — `calt_msg_host` install + ping; SoftLand check **relay** to Python.  
3. **P5a** — Host decides from `study_flags.json` + `softland_policy.json`; Gate prefers native.  
4. **P5b** — Documented later: no live SoftLand HTTP; writers only.

---

## Success criteria (P5a)

- [ ] With API stopped, Gate + host still SoftLand-block a listed domain when flags say study SoftLand active (fail-closed / last flags).  
- [ ] With API up, completing Bible/plan/goal updates flags within seconds and native decision changes without requiring Gate to call `:8000` for mode.  
- [ ] SoftLand toggle never arms `hard_block_armed`.  
- [ ] Rollback: Gate can return to HTTP SoftLand in one config flag.  
- [ ] Webapp (notes, Study Loop UI) unchanged in ownership (Python).

## Out of scope / later

- Full offline SoftLand with no flag file (impossible — need *some* study truth)  
- Porting LLM / planner propose into C++  
- Deleting `distraction_gate.py` (may remain for web Focus “Now” card until UI reads flags too)

---

## Risks

| Risk | Mitigation |
|------|------------|
| Flag schema drifts from Python gate | Single publisher + golden tests: flag cases ↔ expected action |
| Stale flags after midnight | `day` field + TTL; fail closed |
| Host not installed | Gate falls back to HTTP; smoke checklist |
| Partial rule port feels “weaker” SoftLand | Explicit parity table; ship reduced set only if labeled |

---

## Related

- [2026-09-07-calt-blocker-study-split-decisions.md](./2026-09-07-calt-blocker-study-split-decisions.md) — **authoritative** (P5 parked)  
- [AGENTS.md](../../../AGENTS.md) — current focus (P1; not P5a)  
- [2026-09-06-calt-native-enforcer-design.md](./2026-09-06-calt-native-enforcer-design.md) — kills  
- [2026-09-07-one-engine-map.md](./2026-09-07-one-engine-map.md) — options map  
- [2026-09-07-productivity-settings-focus-merge-design.md](./2026-09-07-productivity-settings-focus-merge-design.md) — Settings hub  

---

**Owner:** P5/P5a is **parked**. Do not treat approval of this draft as a green light to build. Reopen only after P1 + optional P4, via the decisions doc.
