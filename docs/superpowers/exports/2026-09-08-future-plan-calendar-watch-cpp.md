# Future — Plan / Calendar / Watch into Productivity C++

**Date:** 2026-09-08 (updated 2026-09-11)  
**Status:** **Unparked** — absorbed into [Focus standalone design](../specs/2026-09-11-calt-focus-standalone-productivity-design.md)  
**Owner intent:** Focus sole door; SoftLand/Arm/Settings correctness first; Calendar/Plan offline via enforcer SQLite

---

## Mapping to Focus standalone phases

| Old tier | Now |
|----------|-----|
| **F1** (tabs only in Focus; Study drops nav) | **Phase 0** — done in standalone plan (interstitial + empty Study nav) |
| Live Settings / gateway | **Phase 1** |
| Unlock / scorer | **Phases 2–3** (P5a/b/c) |
| Browser track + wearables capture | **Phase 4** (wearables stay `:8765` sidecar) |
| Calendar reads without Study | **Phase 5** |
| Planner SQLite + F2 coupling | **Phases 6a / 6b** |
| Stop auto-start Study API | **Phase 7** |
| **F4** full C++ Google/wearables auth | Still **out of scope** |

**Canonical order:** 0 → 1 → 2 → 3 → 4 → 5 → 6a → 6b → 7 → (3b optional)

---

## Success

- Plan/Calendar usable with Focus as the only Productivity door.  
- Active plan block can tighten SoftLand via gateway (6b).  
- No second SoftLand brain in Python.

**Related:** [standalone design](../specs/2026-09-11-calt-focus-standalone-productivity-design.md) · [product lock](../specs/2026-09-07-calt-productivity-cpp-product-design.md) · [BLOCKING_RULES](../../BLOCKING_RULES.md)
