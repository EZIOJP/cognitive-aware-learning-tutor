# Focus Day Loop — design

**Date:** 2026-09-11  
**Status:** Owner-locked — implement Slice 1 → 2 → 3  
**Product:** CALT Focus (Productivity) — SoftLand / Arm / Plan via enforcer pipe only  

## Locked decisions

| Topic | Lock |
|-------|------|
| Morning | Bible → Plan confirm → Goals (native SoftLand goals; no Study `:8000` SoT) |
| Goals | Allow useful sites/apps **and** mark distractions; planned productivity blocks + day task checkboxes in enforcer SoT |
| Landing | Today’s tasks + current SoftLand mode + current plan block |
| Free unlock | Checkboxes **all done** AND tracked productive ≥ **50% of today’s planned block minutes** → **1h** SoftLand free + temporary Arm entertainment allowlist |
| Incomplete | **No** SoftLand duration extend. Carry = optional user prompt only |
| Tomorrow import | Prompt: pull unfinished goal blocks into today vs leave |
| Bedtime | Focus fullscreen sleep surface + Arm/SoftLand hard. **Emergency**: web mostly open, common distractions still blocked; games stay Arm-killed |
| Out of scope | True OS logout; auto time-extend; Study morning-plan file as SoT |

## Architecture

```text
Focus UI → enforcerNativeCmd → \\.\pipe\calt_enforcer_cmd
                │
                ├─ day.confirm_plan / softland.patch_goals
                ├─ day.task_* / day.loop_snapshot
                ├─ day.evaluate_close  (dual gate → free_until +60m)
                ├─ softland.set_bedtime / emergency_winddown
                └─ plan.roll_forward / plan.import_from_date (prompts)

Gate SoftLand decide ← softland_policy.json (bible_done, plan_confirmed, free_until, bedtime_active)
```

## SoftLand / runtime fields (additions)

Under `runtime` (or goals where noted):

- `bedtime_hm` — `"HH:MM"` local  
- `wake_hm` — optional  
- `bedtime_active` — bool (tick sets after bedtime until wake)  
- `closeout_free_granted_date` — `YYYY-MM-DD` once per day  
- `emergency_until` — ISO; SoftLand allow-most with distraction lists kept  
- `entertainment_exes` — optional array for Arm allow during free hour  

## Day tasks SoT

Table `productivity_day_tasks`:

`id, user_id, task_date, title, done, sort_order, created_at`

Ops: `day.task_list`, `day.task_upsert`, `day.task_set_done`, `day.task_delete`.

## Dual-gate free (Slice 2)

```
planned = sum(planner_blocks today where category not in free/break/leisure…)
tracked = productive minutes from day_rollup / sessions (same calendar day)
checkboxes_ok = all day tasks done (or zero tasks → false until user adds & completes, or allow empty=true only if planned>0 and user confirms — lock: empty task list does NOT unlock; require ≥1 task OR skip checkbox gate if zero tasks scheduled)
```

**Lock for empty tasks:** If no day tasks exist, checkbox gate is **satisfied** only when planned_minutes > 0 and user has confirmed plan (plan_confirmed); otherwise checkboxes must all be done. Simpler lock: **if task count == 0, treat checkboxes_done = true** so time gate alone can unlock when user only uses plan blocks. Prefer: **checkboxes_done = (count==0) OR all done**.

Grant once per day: `free_until = now+60m`, set `closeout_free_granted_date`.

## Bedtime (Slice 3)

Tick: if local time ≥ `bedtime_hm` (and before wake) → `bedtime_active=true`, SoftLand study flags, prefer Arm armed if policy says so.  
Emergency: confirm `EMERGENCY` → `emergency_until=now+30m`; decide treats as free for non-distraction hosts; Arm keeps game kills.

## FE surfaces

1. ConfirmPlanButton → native in Focus shell  
2. Goals step → tasks + SoftLandSiteRules + Arm entertainment/kill editors  
3. Landing strip → DayLoopLanding  
4. Closeout prompts → carry / import  
5. BedtimeOverlay fullscreen when `bedtime_active`

## Exit smokes

1. `:8000` killed → bible + plan confirm + goals + landing  
2. Dual gate → 1h free; prompts only for carry/import  
3. Bedtime → overlay; Emergency → browse minus distractions  
