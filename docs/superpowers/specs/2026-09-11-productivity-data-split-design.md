# Focus / Productivity data layout — separate from Study

**Date:** 2026-09-11  
**Status:** Done (2026-09-11)  
**Lock:** Two DBs + Focus-owned folders; Study has zero Bible/Journal

## Layout

```text
data/vocab_app.db              ← Study only (GRE, notes, quizzes, …)
data/productivity/
  productivity.db              ← SoftLand, planner, sessions, journal, bible progress
  behavior/                    ← mirrors (was data/behavior/)
  bible/                       ← WEB corpus (was data/bible/)
```

`CALT_DB` default → `data/productivity/productivity.db`  
Behavior dir = sibling `behavior/` of that DB.  
Bible dir = sibling `bible/`.

## Study strip

- No `/bible` / `/journal` in Study (redirect home if hit)
- Unmount Study FastAPI bible + journal routers
- Focus keeps Bible/Journal UI via Focus shell only
