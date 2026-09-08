# Future (thin) — Plan / Calendar / Watch deeper into Productivity C++

**Date:** 2026-09-08  
**Status:** Parked — do **not** start until Settings Figma + React overhaul ships  
**Owner intent:** Better one-app feel and plan↔blocking coupling, without a full rewrite now

---

## Not now

Rewriting Plan, Calendar, Google sync, LLM propose, or wearables ingest into C++ is **out of scope** for the current Settings pass. Calendar/Plan stay **Python API + React UI**.

---

## Tiered future work (when ready)

| Tier | What | Approx cost | Blocking payoff |
|------|------|-------------|-----------------|
| **F0 (done-ish)** | SoftLand / Arm / lists / schedules via enforcer gateway; Focus shell hosts React | — | High (already) |
| **F1** | Productivity + Plan + Calendar + Watch **tabs only in `calt_focus`** (Study sidebar drops them); logic still Python HTTP | 1–2 weeks | Low (UX only) |
| **F2** | Plan blocks / day rhythm → SoftLand schedule or mode via **gateway events** (study/plan emits; C++ applies) | 2–3 weeks | Medium |
| **F3** | Planner + wearables rollups in enforcer SQLite; Python becomes thin/optional for LLM + Google OAuth | 6–10 weeks | Medium–high offline |
| **F4** | Full C++ rewrite of planner + Google + wearables | 3–5+ months | Low extra vs F3 |

**Recommended order when unparking:** F1 with Settings polish → F2 → (optional) F3. Skip F4 unless product lock changes.

---

## Success when unparked

- Plan/Calendar usable with Focus as the only Productivity door (F1).  
- Active study block can tighten SoftLand without opening Study Settings (F2).  
- No second SoftLand brain in Python.

**Related:** [product lock](../specs/2026-09-07-calt-productivity-cpp-product-design.md) · [BLOCKING_RULES](../../BLOCKING_RULES.md) · [Settings architecture note](./2026-09-08-productivity-settings-architecture-note.md)
