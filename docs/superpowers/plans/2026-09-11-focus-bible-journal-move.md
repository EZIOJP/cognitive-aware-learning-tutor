# Focus Bible + Journal Move — Implementation Plan

> **For agentic workers:** Use subagent-driven-development or execute task-by-task.  
> **Spec:** [2026-09-11-focus-bible-journal-move-design.md](../specs/2026-09-11-focus-bible-journal-move-design.md)

**Goal:** Move Bible + Journal into Focus with enforcer gateway SoT; strip Study doors and Python SoftLand bible reads.

**Architecture:** Reuse planner transport pattern (`isFocusDesktopShell` → `enforcerNativeCmd`). Journal reuses `journal_entries` table. Bible progress in SQLite + chapter slices from `data/bible/structured/`. SoftLand `goals.bible_done` set only by enforcer.

**Tech Stack:** C++ `calt_enforcer` gateway, React Focus shell, existing Bible/Journal React pages.

## Global Constraints

- SoftLand ≠ Arm naming unchanged  
- No CT code  
- Study `:8000` not required for Focus Bible/Journal  
- Commits only if user asks  

## Tasks

### J1 Journal gateway + Focus client
- [ ] `journal.list` / `journal.upsert` / `journal.delete` in `cmd_gateway.cpp` + store helpers
- [ ] `src/api/journalClient.ts` Focus pipe path
- [ ] Focus sidebar Journal; Study `/journal` interstitial

### B1 Bible gateway + Focus client
- [ ] `bible.today` / `bible.chapter` / `bible.tick` (+ minimal meta)
- [ ] Import legacy day JSON once if needed; SQLite SoT for progress
- [ ] `bibleClient.ts` Focus pipe path; Focus sidebar Bible

### B2 SoftLand strip Python bible
- [ ] SoftLand/morning/`distraction_gate` read `goals.bible_done` from softland mirror / native — no `bible.store`
- [ ] Smoke: bible tick → softland_policy `bible_done`

### S1 Study strip + docs
- [ ] Remove Study nav entries; interstitial for `/bible` `/journal`
- [ ] Update AGENTS.md + standalone design + BLOCKING_RULES note
- [ ] `npm run build:focus`; rebuild enforcer

## Exit
`:8000` stopped → Focus Journal CRUD + Bible read/tick + SoftLand bible_done work.
