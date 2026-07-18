# Mental Math Aptitude Ladder — Design

**Date:** 2026-07-17  
**Decision:** Dynamic generation (not pre-generated banks).

## Why dynamic
- Weight weak factors from live `MathAttempt` history
- Infinite variety without maintaining hundreds of static items
- Attach strategy hints per concrete problem
- Evolve modes (forward / reverse / estimate / family) from the same skill params

Pre-generated banks stay for imported textbooks / OCR train targets only.

## Curriculum (ordered unlock)
1. `times_1_20` — Core times 3–20, **exclude factors 1, 2, 10**
2. `times_21_50` — Stretch 21–50 × 3–12 (no 1/2/10)
3. `mental_shortcuts` — near-10/100 and split products with strategy hints
4. `squares_upto_50` — n², n ≤ 50
5. `cubes_upto_20` — n³, n ≤ 20
6. `powers_4_upto_10` — n⁴, n ≤ 10
7. `powers_5_upto_5` — n⁵, n ≤ 5
8. `powers_mixed` — base &lt; 10, exponent 2–6
9. `powers_8_important` — bases {2,3,5,10} only, exp 8
10. `times_estimation` — choose closest estimate
11. `times_reverse` — find missing factor
12. `times_fact_family` — × and ÷ family around one product
13. Existing: division → divisibility → lcm/gcd → fractions → % (after core times)

## Mastery
- Accuracy: last 20 attempts ≥ 85% (existing)
- Speed unlock: median `time_taken_ms` of those 20 correct-enough window ≤ 8000 ms
- Both required to unlock children that set `"require_speed": true`

## Adaptive
- Parse missed prompts for factors/bases; boost sampling weight
- On wrong answer in-session: show strategy hint; requeue once

## Daily mixed (optional node)
- `daily_mixed_5` — available when core times unlocked; 5 items: weak + current + 1 stretch
