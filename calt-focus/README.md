# CALT Focus — Productivity product

**Start here** for architecture, product idea, and where code lives.  
Study (GRE / notes / math / Study Loop content on `:8000`) is a **different product** — do not review it as SoftLand.

---

## Idea (why Focus exists)

You wanted a **Cold Turkey–class productivity app** that:

1. **Blocks distractions** (sites SoftLand + OS app kills) without depending on a study web server  
2. **Plans the day** (Calendar / Plan / routines) in the same desk app  
3. **Owns life blockers** that unlock SoftLand (Bible chapter done, Journal)  
4. Stays **local-first** — SQLite + JSON mirrors under `data/productivity/`, named-pipe writes only through `calt_enforcer`

**Two products forever**

| Product | Door | Owns |
|---------|------|------|
| **CALT Focus** (this folder) | `calt_focus.exe` tray + WebView2 | SoftLand, Arm, Plan, Calendar, Settings, Bible, Journal, Gate decide |
| **CALT Study** | Browser `:8000` / Vite | GRE, notes, math, Study Loop *content* only |

Naming lock: `softland_enabled` = sites only. `hard_block_armed` = OS kill switch. SoftLand ON ≠ Arm.

---

## Architecture (whole Focus app)

```text
┌─────────────────────────────────────────────────────────────┐
│  calt_focus.exe  (tray + WebView2 → dist-focus / calt.app)   │
│  UI: Calendar · Plan · Settings · Focus · Bible · Journal     │
│  reads:  https://calt-data.app  → data/productivity/behavior │
│  writes: enforcerNativeCmd → \\.\pipe\calt_enforcer_cmd      │
└────────────────────────────┬────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────┐
│  calt_enforcer.exe  (ZERO Python)                             │
│  SoftLand SoT · Arm/kills · sessions · planner · bible/journal│
│  DB: data/productivity/productivity.db                        │
│  mirrors: data/productivity/behavior/*.json                   │
└───────────────┬─────────────────────────────┬───────────────┘
                │                             │
                ▼                             ▼
┌───────────────────────────┐   ┌─────────────────────────────┐
│ calt_msg_host.exe         │   │ Edge extensions             │
│ Gate SoftLand get_mode    │   │ Gate + SelfTracker          │
│ + track_tab → SQLite      │   │ (native messaging)          │
└───────────────────────────┘   └─────────────────────────────┘

Optional (not required for SoftLand/Arm/Plan):
  Study :8000  — Google OAuth, LLM propose, Study content
  :8765        — wearables hub sidecar
```

**Data layout**

```text
data/productivity/
  productivity.db     ← SoftLand, planner, sessions, journal, bible progress
  behavior/           ← softland_policy.json, enforcer_*.json, day_rollup.json
  bible/              ← chapter corpus (FE via calt-bible.app)
data/vocab_app.db     ← Study only (not SoftLand SoT)
```

---

## Repo map (this folder)

```text
calt-focus/
  README.md          ← you are here (architecture + idea)
  frontend/          ← Vite design host entry (FE build)
  backend/           ← C++ enforcer + Focus shell + msg-host (BE)
  extensions/        ← Gate + SelfTracker
```

| Layer | Open | Role |
|-------|------|------|
| FE | [frontend/README.md](./frontend/README.md) | `npm run build:focus` / `dev:focus`; shared React still under repo `src/` |
| BE | [backend/README.md](./backend/README.md) | SoftLand/Arm/Plan/Bible/Journal SoT |
| Ext | [extensions/README.md](./extensions/README.md) | Browser Gate + track |

`native/` at repo root is a **redirect only** — real natives are under `calt-focus/backend/`.

---

## How to run

```bat
npm run build:focus
scripts\desktop_tracker\build\build_native_enforcer.bat
scripts\desktop_tracker\build\build_native_focus.bat
scripts\desktop_tracker\build\build_calt_msg_host.bat
scripts\desktop_tracker\run\run_calt_desktop.bat
```

- Design host (UI only): `npm run dev:focus` → http://127.0.0.1:5180/  
- SoftLand/Arm/Plan **writes** need `calt_focus.exe` + enforcer pipe (design host cannot mutate)  
- Tray: Productivity menus first; Study `:8000` / Vite under **Advanced**

---

## Specs & deeper context (read in this order)

| Doc | What it is |
|-----|------------|
| **This file** | Idea + architecture + map |
| [AGENTS.md](../AGENTS.md) | Repo-wide product lock (two products) |
| [Focus standalone design](../docs/superpowers/specs/2026-09-11-calt-focus-standalone-productivity-design.md) | Phased door cutover 0→7 |
| [Landing / what works offline](../docs/superpowers/exports/2026-09-11-focus-standalone-landing.md) | Smoke checklist |
| [Data split](../docs/superpowers/specs/2026-09-11-productivity-data-split-design.md) | `productivity.db` vs Study DB |
| [Bible/Journal → Focus](../docs/superpowers/specs/2026-09-11-focus-bible-journal-move-design.md) | Life content ownership |
| [UX polish](../docs/superpowers/specs/2026-09-11-calt-focus-ux-polish-design.md) | Design host, plan cards |
| [BLOCKING_RULES.md](../docs/BLOCKING_RULES.md) | How SoftLand / Arm / unlocks actually behave |
| [Productivity C++ product](../docs/superpowers/specs/2026-09-07-calt-productivity-cpp-product-design.md) | Original product lock |
| [SoftLand state model](../docs/superpowers/specs/2026-09-07-calt-productivity-softland-state-model.md) | Policy document shape |

---

## What Focus does *not* own

- GRE / notes / math / Study Loop quiz content → Study  
- LLM week propose / Google Calendar OAuth → optional Study `:8000` (tray Advanced)  
- Wearables phone ingest → `:8765` sidecar  
- No Cold Turkey source code — pattern language only
