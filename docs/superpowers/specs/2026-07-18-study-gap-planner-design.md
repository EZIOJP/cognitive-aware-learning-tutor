# Study gap planner — routines → gaps → 50m packs → AI review → reward → adherence

**Date:** 2026-07-18  
**Status:** Approved (user “ok”)  
**Approach:** C — algorithm builds plan; AI reviews; adherence adjusts future load

## Goal

Plan study hours into free time after routines without overstudying, hit the daily focus goal when gaps allow, unlock a visible reward when the day is complete, and gently adjust future planned load from how well the user followed recent plans.

## Pipeline

```text
1. Goals          daily hours + reward copy (existing productivity:goals:v1)
2. Routines       locked busy intervals (enabled routines)
3. Gap algorithm  pack ~50m study + breaks until daily goal minutes
4. AI review      optional polish (keep routines, hours, no entertainment-as-study)
5. Apply          write blocks to planner calendar
6. Live day       effective focus vs daily goal
7. Reward UI      visual unlock when goal met (+ existing entertainment gate)
8. Next propose   adherence-based load adjust (last ~7 days)
```

## Constraints (mind protection)

| Rule | Value |
|------|--------|
| Study chunk | ~50 minutes (45–55 ok) |
| Break | Short break after each chunk (or every 2 chunks) |
| Continuous deep work | Cap ~100 minutes before a break is required |
| Daily ceiling | Do **not** plan study past daily goal minutes |
| Shortfall | If free gaps &lt; goal → fill usable gaps + report shortfall honestly |
| Categories | Never schedule Gaming / entertainment / social as study |

## Gap algorithm (deterministic)

1. Materialize enabled routines for the horizon as busy.  
2. Merge in existing calendar blocks as busy.  
3. Compute free gaps in a day window (e.g. 06:00–23:00).  
4. Pack left-to-right into gaps:
   - Prefer **50m** study chunks labeled from **goals only** (Scaler lessons / practice / AI-ML — not tracker top categories).
   - Insert short breaks so the day is recoverable.
   - Stop when planned study minutes ≥ daily goal (weekend soft trim optional, ~90% of daily).  
5. Second pass with slightly smaller chunks only if still short of goal and gaps remain.  
6. Filter any unproductive labels before return.

Study titles come from goal keywords / extras only — never from tracker “top categories” (avoids “Deep work · Gaming”).

## AI role

- **Optional review** after smart pack: rename/move study blocks, fill leftover shortfall if safe, keep routines.  
- **Not** the primary scheduler. If LLM fails, keep the algorithm draft.

## Reward

1. **Policy gate (existing):** entertainment unlock after today’s effective-focus ≥ daily goal.  
2. **Visual unlock (new):** clear “Reward unlocked” state on Plan / Today when the goal is met (copy from Goals.reward).

## Adherence → load adjust

Using last ~7 days plan-vs-actual (existing export / adherence):

| Recent study adherence | Next smart daily target |
|------------------------|-------------------------|
| ≥ 80% of planned       | Full daily goal hours |
| 60–80%                 | ~90% of daily goal |
| &lt; 60%               | ~80% of daily goal |

Badge still shows the user’s stated goal vs planned (“Today Xh / 4h goal · short …”) so load adjust is transparent.

## UI (Plan step 3)

1. **Build smart** — run gap algorithm (primary CTA).  
2. **AI review draft** — polish after a draft exists.  
3. Review editor — agenda + day strip; hours badge; no gaming study.  
4. Apply → calendar.  
5. Finish / Today — reward unlock when goal met.

## Non-goals

- Full BKT / psychometric models  
- Auto-deleting or rewriting user routines  
- AI-only calendars as the default path  
- Forcing 4h into a day that literally has &lt;4h free without user consent  

## Success criteria

- [ ] With routines + 4h daily goal, smart plan schedules ~4h **productive** study when gaps allow (or honest shortfall).  
- [ ] No study block titled/categorized as Gaming/entertainment.  
- [ ] Chunks ≈ 50m with breaks; no solid multi-hour wall without breaks.  
- [ ] Visual reward unlock appears when daily focus goal is met.  
- [ ] Next propose softens load after weak adherence weeks.  
- [ ] Unit tests cover: no gaming titles, gap pack hits hours when free, breaks inserted.

## Touch points

- `backend/planner/llm_propose.py` — gap pack, titles, adherence scale  
- `backend/planner/router.py` — busy calendar + propose modes  
- `src/pages/ProductivityPage.tsx` / `ProposePlanPreview.tsx` — CTAs, hours badge  
- Goals / Today / policy panels — visual reward unlock  
- Tests in `tests/test_productivity_policy.py` (or dedicated planner tests)

## Related

- `docs/superpowers/specs/2026-07-18-plan-multi-goals-design.md` — goals + Plan flow order  
