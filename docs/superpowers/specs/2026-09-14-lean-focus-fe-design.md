# Lean Focus FE (separate app until product finalized)

**Date:** 2026-09-14  
**Status:** Owner-approved approach A — **landed** (lean `FocusApp` entry; main JS ~1.7 MB vs ~5.6 MB prior)  
**Problem:** Tab switches / shell chrome in `calt_focus.exe` feel slow because `build:focus` ships the shared Study+Focus React tree (~5–6 MB main JS: Mermaid, KaTeX, Cytoscape, plugins, GRE/math routes, etc.).  
**Builds on:** [Focus standalone](./2026-09-11-calt-focus-standalone-productivity-design.md), [ultra-low-latency control plane](./2026-09-14-focus-ultra-low-latency-design.md)  
**Does not replace:** C++ enforcer SoT, named-pipe writes, status bus / mirrors.

---

## 1. Success definition

1. WebView2 loads a **Focus-only** SPA from `dist-focus/` with **no Study feature graph** in the main bundle.
2. Tab switches (Home ↔ Calendar ↔ Plan ↔ Settings ↔ Focus ↔ Bible ↔ Journal) feel snappy on this machine (target: no multi-second freezes; main chunk **&lt; ~1.5 MB uncompressed**, prefer **&lt; ~500 KB gzip**).
3. Tray deep-links (`?tab=…`, HashRouter, `https://calt.app`) keep working.
4. SoftLand / Arm / Plan writes still go through `enforcerNativeCmd` → `\\.\pipe\calt_enforcer_cmd`; status prefers mirrors + `focusStatusBus` (no new SoftLand brain).
5. Study `:8000` keeps the full shared `src/` app unchanged for content workflows.

---

## 2. Architecture

```text
calt_focus.exe (unchanged shell)
    │  WebView2 → dist-focus → https://calt.app
    │
    ▼
Lean Focus SPA  (NEW entry under calt-focus/frontend/)
    │  routes: productivity tabs only
    │  imports: productivity clients + components via alias
    │  NO: GRE, notes, math, quiz, plugin marketplace, mermaid/katex/cytoscape
    │
    ├─ read:  calt-data.app / mirrors / focusStatusBus
    └─ write: enforcerNativeCmd → calt_enforcer pipe

Study Vite (:8000)  — full shared src/ (unchanged)
```

### Layout

```text
calt-focus/frontend/
  vite.config.ts          ← root = lean app (not repo root)
  index.html
  app/
    main.tsx
    FocusApp.tsx          ← HashRouter + tab shell only
    FocusShell.tsx        ← minimal chrome (sidebar/topbar lite)
  README.md               ← update: lean app is the ship path
```

Shared logic stays in repo `src/` (clients, productivity components, bus). Lean app **imports selectively**; Vite must not crawl Study entry (`src/main.tsx` / full `App.tsx` Study tree).

---

## 3. Product surface (in)

| Tab / route | Source strategy |
|-------------|-----------------|
| Home | Existing `HomeModeBoard` / productivity home pieces |
| Calendar / Plan | `PlannerCalendar` + planner clients |
| Settings | Focus Settings hub (SoftLand / Arm / lists) |
| Focus control | Focus control panel |
| Bible / Journal | Existing Focus-moved pages/clients |

Preserve query `?tab=` and hash routes used by tray / `paths.cpp`.

---

## 4. Explicitly out (until product finalized)

- GRE, vocab, math, notes, Study Loop content UI  
- Plugin marketplace / SuperMermaid / KaTeX / Cytoscape / human.esm  
- Visual redesign / new design system  
- Moving SoftLand decide to HTTP/` :8000`  
- Forking C++ APIs  

If a productivity component hard-imports a Study-only module, **cut or lazy-guard** that edge in the lean graph (prefer thin wrappers over shipping Study deps).

---

## 5. Build & run

| Command | Behavior |
|---------|----------|
| `npm run build:focus` | Build lean app → `dist-focus/` |
| `npm run dev:focus` | Dev server `:5180` for lean app + calt-data middleware |
| `calt_focus.exe` | Unchanged; loads `dist-focus` |

Optional later: `build:focus:legacy` pointing at old shared entry for emergency rollback (not required for v1 if git revert is enough).

---

## 6. Latency contract (FE)

- Main bundle excludes Study plugins and diagram stacks.  
- Route/tab panels: prefer lightweight mounts; heavy calendar work stays on Calendar/Plan only (already mostly true).  
- Keep **one** status bus; do not reintroduce per-panel pipe spam (see ultra-low-latency design).  
- Focus host pipe reader already drains large `plan.overlay` messages; lean FE still must not poll overlay on every tab.

---

## 7. Verification

1. `npm run build:focus` — report main chunk size vs baseline (~5.6 MB).  
2. Manual: open Focus tray → switch Home / Calendar / Plan / Settings repeatedly — no multi-second hitch.  
3. Gateway smoke: SoftLand toggle, Arm status chip, Calendar shows plans + tracked chips (hour_slices FE builder).  
4. Confirm Study `:8000` still builds/runs separately.  
5. `npx vitest` for any new lean-entry smoke / import-boundary test (optional but preferred: fail CI if lean entry resolves `mermaid` / `katex`).

---

## 8. Rollout

1. Land lean entry + Vite root switch.  
2. Rebuild `dist-focus`, restart `calt_focus.exe`.  
3. If a tab is incomplete, stub with “open later” only as last resort — prefer wiring existing productivity components.  
4. Document in `calt-focus/README.md` + `frontend/README.md`: Focus ships lean FE; shared `src/` remains library + Study.

---

## 9. Non-goals / risks

| Risk | Mitigation |
|------|------------|
| Accidental import of Study `App.tsx` | Separate `FocusApp.tsx`; build analyzer / denylist |
| Duplicate styling / missing glossy CSS | Import only productivity + glossy entry CSS needed |
| Drift between Study interstitial productivity and Focus | Shared components stay in `src/`; only shells differ |
| Bundle still large via transitive deps | Treat &gt;1.5 MB main as ship blocker; chase imports |

---

## 10. Decision lock

**Owner chose A (2026-09-14):** separate lean Focus FE until the productivity app is finalized; prioritize no UI lag over maximizing code reuse in one SPA.
