# Lean Focus FE Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans or implement directly. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship a Focus-only SPA in `dist-focus/` that excludes Study plugins/diagram stacks so tab switches no longer lag.

**Architecture:** New Vite root under `calt-focus/frontend/` with `FocusApp.tsx` (HashRouter + productivity/bible/journal only). Import shared productivity components from `src/` via alias; never import `src/plugins` or Study `App.tsx`.

**Tech Stack:** Vite 6, React 18, HashRouter, existing `enforcerNativeCmd` / `focusStatusBus`

**Spec:** [docs/superpowers/specs/2026-09-14-lean-focus-fe-design.md](../specs/2026-09-14-lean-focus-fe-design.md)

## Global Constraints

- Main chunk ship blocker: >1.5 MB uncompressed
- SoftLand writes only via named pipe
- Preserve `?tab=` and tray URLs
- Study `:8000` entry unchanged

---

### Task 1: Lean Vite entry + FocusApp shell

**Files:**
- Create: `calt-focus/frontend/index.html`, `app/main.tsx`, `app/FocusApp.tsx`, `app/FocusShell.tsx`
- Modify: `calt-focus/frontend/vite.config.ts`, `calt-focus/frontend/README.md`, `calt-focus/README.md`

- [x] Scaffold lean entry (no plugins import)
- [x] Wire HashRouter routes: `/productivity`, `/journal`, `/bible/*`, default → productivity?tab=home
- [x] Point vite root at frontend folder; alias `@` → repo `src`
- [x] `npm run build:focus` and measure chunk size (**~1.73 MB / 506 KB gzip** vs prior ~5.6 MB)
- [x] Restart calt_focus and smoke tab switches

---
