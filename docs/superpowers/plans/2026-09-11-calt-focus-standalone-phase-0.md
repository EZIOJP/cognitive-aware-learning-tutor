# Phase 0 — Focus sole door (Study productivity cutover)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `calt_focus` the only Productivity door; Study browser shows an interstitial for `/productivity*`.

**Architecture:** Empty Study plugin nav; routes remain but render interstitial when `!isFocusDesktopShell()`. Focus top bar gains "Open Study". Freeze: no Study productivity mutators from browser after this.

**Tech Stack:** React, React Router, existing `focusDesktopShell.ts`

**Spec:** [2026-09-11-calt-focus-standalone-productivity-design.md](../specs/2026-09-11-calt-focus-standalone-productivity-design.md) Phase 0 (decisions 5A, 11B, 12A, 15A)

## Global Constraints

- Nav-only chrome change (do not strip Pomodoro/face docks).
- Routes stay in the Study bundle (no Focus-only chunk).
- No commits unless user asks.

---

### Task 1: Study plugin nav empty

**Files:** `src/plugins/productivity_plugin.tsx`

- [ ] Set `navItems: []` so Study sidebar no longer lists Calendar/Focus.
- [ ] Keep routes registered (paths still resolve).

### Task 2: Interstitial component

**Files:** create `src/components/productivity/OpenFocusInterstitial.tsx`

- [ ] Copy explains Productivity lives in CALT Focus desktop app.
- [ ] CTA: instructions to open tray / `calt_focus.exe` (no fake protocol required).
- [ ] Optional link to open Study home `/` for confusion recovery.

### Task 3: Gate Productivity routes in Study shell

**Files:** `src/plugins/productivity_plugin.tsx` and/or thin wrappers

- [ ] When `!isFocusDesktopShell()`, render `OpenFocusInterstitial` instead of `ProductivityPage` / `FocusPage`.
- [ ] When Focus shell, unchanged pages.

### Task 4: Open Study in Focus top bar

**Files:** `src/layout/AppTopBar.tsx`

- [ ] If `isFocusDesktopShell()`, show "Open Study" control that opens Study in system browser (`http://127.0.0.1:5173/` or `http://127.0.0.1:8000/` — prefer Vite FE if known; use `window.chrome.webview` host message if available, else `window.open`).
- [ ] Decision 11B: do not remove Pomodoro/face docks.

### Task 5: Docs

**Files:** `AGENTS.md`, `docs/superpowers/exports/2026-09-08-future-plan-calendar-watch-cpp.md`

- [ ] Note Phase 0 in progress / door freeze.
- [ ] Unpark F1 note pointing at umbrella spec.

### Task 6: Verify

- [ ] Mentally / manually: Study sidebar has no Calendar/Focus; `/productivity` shows interstitial.
- [ ] Focus shell still shows productivity UI.
