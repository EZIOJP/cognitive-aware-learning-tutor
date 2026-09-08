# After P5a — ordered next work

**Date:** 2026-09-09  
**Context:** Settings UI is shipped (React + visual polish). Unlock accounting **P5a** is designed but not built.

## Right after P5a (same Prod P5)

| Step | What | Why |
|------|------|-----|
| **P5a** | Day-pass / reward / earn rates / incubation limits in `calt_enforcer` + fix day-pass → free window | Unlocks work with `:8000` stopped; fixes pass not opening sites |
| **P5b** | Native classification + productive minutes (rules-as-data, sleep mirror, day rollup) | One scorer — no Python/UI disagreement |
| **P5c** | Native qualification; Python reads rollup only | Streak credit with API down all day |

**Spec:** [P5 design](../specs/2026-09-08-calt-productivity-p5-native-unlock-accounting-design.md)  
**P5a plan:** [P5a plan](../plans/2026-09-08-calt-productivity-p5a-native-unlock-accounting.md)

## After full P5

| Item | Status |
|------|--------|
| **Prod P6** | Browser track without Python |
| **F1** | Plan/Calendar/Watch tabs only in Focus (logic still Python) |
| **F2** | Plan block → SoftLand via gateway events |
| **F3** | Planner/wearables rollups in enforcer SQLite (optional) |
| **F4** | Full C++ planner rewrite — skip unless product lock changes |

**Parked detail:** [future Plan/Calendar/Watch](./2026-09-08-future-plan-calendar-watch-cpp.md)

## Recommended order

1. Live with polished Settings a few days  
2. **P5a** (highest daily-use bug fix)  
3. P5b → P5c  
4. P6 when browser track without Python matters  
5. F1/F2 only if you want Plan glued tighter to SoftLand
