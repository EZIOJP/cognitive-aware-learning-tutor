# Focus owns Bible + Journal — move out of Study

**Date:** 2026-09-11  
**Status:** Implemented (J1/B1/B2/S1 landing)  
**Supersedes (for Bible/Journal door):** [2026-09-11-calt-focus-standalone-productivity-design.md](./2026-09-11-calt-focus-standalone-productivity-design.md) §1 “Study remains… Bible… Journal” and “Out of scope: Porting GRE / Bible / Journal…”  
**Builds on:** Productivity C++ product lock, enforcer gateway, Focus shell nav

---

## 1. Intent

**Move** Bible and Journal out of CALT Study into CALT Focus. They are life / SoftLand rituals, not study content. Permanence = **C++ enforcer SoT** — Focus works with Study `:8000` stopped.

Study keeps: GRE, notes, math, quizzes, Study Loop.

---

## 2. Product doors

| App | Owns after move |
|-----|-----------------|
| **Focus** (`calt_focus`) | Calendar, Plan, Settings, Focus controls, **Bible**, **Journal** |
| **Study** (`:8000` + Vite `:5173`) | GRE / notes / math / quizzes only — **no** Bible or Journal nav, routes, or SoftLand bible SoT |

Study `/bible` and `/journal` → interstitial **Open in Focus** (same pattern as Study `/productivity*`).

---

## 3. Architecture

```text
calt_focus WebView2
  ├── React Bible + Journal pages (moved into Focus nav)
  ├── chapter text: map data/bible/  OR  gateway bible.chapter
  └── mutations: enforcerNativeCmd → \\.\pipe\calt_enforcer_cmd

calt_enforcer
  ├── journal_* tables in data/vocab_app.db
  ├── bible progress / bookmarks / day ticks in SQLite (migrate off day_*.json as SoT)
  ├── verse corpus: read-only files under data/bible/structured/ (WEB)
  └── SoftLand goals.bible_done + morning ladder from native progress only

Study Python
  └── Stop importing backend.bible.store for SoftLand / distraction_gate / morning.
      Optional: delete or leave dead HTTP routers until cleanup pass.
```

**Bible read logic (C++ — keep simple)**  
- `bible.chapter` / `bible.today` / `bible.tick` / `bible.heartbeat` on the gateway  
- Chapter body: load from `data/bible/structured/web.json` (or per-chapter cache files) in-process — no FastAPI  
- Day goal met → set `goals.bible_done` in SoftLand SoT (already mirrored)  
- No Python `store.summary()` on the live SoftLand path

**Journal (C++ — thin)**  
- `journal.list` / `journal.upsert` / `journal.delete` over existing `journal_entries` (or `productivity_journal_*` if isolation preferred — default = **reuse table**, enforcer is sole writer from Focus)

---

## 4. SoftLand / Study strip (locked this design)

1. **Focus nav:** add Bible + Journal next to Calendar / Plan / Settings / Focus.  
2. **Study nav:** remove Bible + Journal entries; deep links interstitial → Focus.  
3. **SoftLand Python bible reads:** remove `backend.bible.store` usage from `distraction_gate` / morning / reward paths that still decide SoftLand. Native enforcer (and Focus UI) own `bible_done`.  
4. **Study API bible/journal routers:** not required for Focus; mark deprecated / stop mounting when Focus path is green (cleanup phase).

---

## 5. Phases

| Phase | Deliverable |
|-------|-------------|
| **J1** | Gateway `journal.*` + Focus Journal page via pipe; Study Journal → interstitial |
| **B1** | Gateway `bible.chapter` / `bible.today` / `bible.tick` (+ bookmarks if needed); Focus Bible page via pipe; corpus from disk |
| **B2** | SoftLand / morning use native `bible_done` only — **strip Python bible reads** |
| **S1** | Strip Study routes/nav for both; AGENTS.md + standalone design update |

Exit: Kill `:8000` → Focus Bible read + tick + Journal CRUD + SoftLand bible_done still work.

---

## 6. Out of scope (first landing)

- GRE / Notes / Math into Focus  
- Zepp `packages/calt-bible` rewrite  
- Native LLM  
- Reintroducing Python kills  
- Full deletion of `backend/bible` Python package on day one (deprecate after B2 green)

---

## 7. Risks

| Risk | Mitigation |
|------|------------|
| WEB JSON size / pipe payload | Serve chapter slices only; or WebView2 file map for corpus + pipe for progress |
| Dual-write during migrate | Enforcer imports legacy `day_*.json` once; then SQLite is SoT |
| Study bookmarks/auth JWT | Focus uses enforcer; no JWT for these ops |

---

## 8. Doc updates after landing

- `AGENTS.md` — Study content list drops Bible/Journal; Focus owns them  
- Focus standalone design — remove “do not port Bible/Journal”  
- `docs/BLOCKING_RULES.md` — bible_done source = native
