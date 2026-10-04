# Confirm plan starts blocking — design

**Date:** 2026-09-15  
**Status:** Owner-locked (Approach 1)  
**Product:** CALT Focus / Productivity (C++)

## Locked decisions

| Topic | Lock |
|-------|------|
| Confirm plan | After Bible: turn **SoftLand on** + **Arm on** together. SoftLand ≠ Arm (separate engines); Confirm couples activation only. |
| Plan ledger | **Remove** the ~10 min `plan_confirmed` ledger earn. Confirm is a gate, not a reward. |
| Study day | Schedules (e.g. Mon–Fri 09:00–18:00 study) apply once SoftLand is on. Watch list (YouTube) blocks in study mode. |
| Free when | Daily productive minutes ≥ `goals.daily_focus_minutes` → set `goals.goal_met`, `free_until` = end of local day (once per day). SoftLand stays on; decide uses free mode. Arm stays armed (games kills); no auto-disarm. |
| Free / reward day | After Bible, at the **plan window**: claim reward day (`REWARD`) or day pass (`PASS`) without a study Confirm. Enables SoftLand + free_until EOD; sets `plan_confirmed` so morning advances. Does **not** require Arm-on (leisure day). |
| Dual-gate 1h | Keep existing `day.evaluate_close` as an optional early 1h free; goal-met EOD free is the primary “goals reached” door. |
| Winddown | Unchanged: bedtime / emergency paths. |

## Day flow

```text
Bible tick → Plan window
  ├─ Confirm plan  → SoftLand ON + Arm ON → study until goal_met → free_until EOD → bedtime
  ├─ Claim REWARD  → SoftLand ON + free day (no forced Arm)
  └─ Spend PASS    → SoftLand ON + free day (no forced Arm)
```

## Implementation surfaces

- `DayLoopConfirmPlan` — enable SoftLand, write Arm policy armed, drop ledger credit; require `bible_done`
- `DayLoopTick` — grant goal-met EOD free once/day
- `day_rollup` — `goal_met` uses `daily_focus_minutes` (not hardcoded 60)
- `reward.claim` / day-pass spent — SoftLand on + `plan_confirmed` when Bible done
- Focus `ConfirmPlanButton` — free-day actions beside Confirm

## Out of scope

- Merging SoftLand and Arm into one switch
- Auto-disarm Arm when goal met
- Changing schedule window definitions
