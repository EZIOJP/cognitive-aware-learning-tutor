# Mental Math Aptitude — Implementation Plan

**Date:** 2026-07-17  
**Approach:** Dynamic generation (approved)

## Done
1. `backend/math/skills.json` v2 — curriculum ladder (core times → stretch → shortcuts → squares → cubes → powers → estimation/reverse/families → daily mixed → division/fractions)
2. `backend/math/generators/layer0.py` — exclude 1/2/10, powers, shortcuts, estimate, reverse, fact family, strategy hints, bias factors
3. `backend/math/skills.py` — weak-factor adaptive sampling, speed mastery (median ≤ 8s when `require_speed`), `generate_drill_items(..., db, user_id)`
4. `backend/quiz/handler.py` — adaptive start, strategy feedback + speed tiers, math requeue on miss, `recent_ms` / `weak_factors` on hub node
5. Tests in `tests/test_math_skills.py`

## How to use
Review Hub → Start quiz → pick skill (e.g. Core times, Squares, Daily mixed) → write/OCR answers → wrong items reappear with strategy tips.
