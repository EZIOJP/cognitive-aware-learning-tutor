# CALT Focus (Productivity product)

**Review entry for another AI / human.** This folder is the map — code still lives in the paths listed below (same git repo as Study). Do **not** review GRE, notes, math, quiz, or Study `:8000` routes unless a Focus file imports them.

| Layer | Role | Tech |
|-------|------|------|
| **Frontend** | Calendar / Plan / Settings / Focus / Bible / Journal UI | React → `dist-focus/` in WebView2 |
| **Backend** | SoftLand, Arm, kills, planner SoT, Bible/Journal SoT, Gate decide | C++ `calt_enforcer` + `calt_msg_host` + Focus shell |

Study (`backend/` FastAPI `:8000`) is **not** the SoftLand brain. Optional only under tray **Advanced**.

---

## Quick review scope

1. Read [FRONTEND.md](./FRONTEND.md) then [BACKEND.md](./BACKEND.md)
2. Ignore Study content under `src/pages/vocab`, `src/pages/math`, notes, quiz plugins
3. Runtime data (local, gitignored): `data/productivity/{productivity.db,behavior/,bible/}`

## Build / run

```bat
npm run build:focus
scripts\desktop_tracker\build\build_native_enforcer.bat
scripts\desktop_tracker\build\build_native_focus.bat
scripts\desktop_tracker\build\build_calt_msg_host.bat
scripts\desktop_tracker\run\run_calt_desktop.bat
```

Design host (FE only, no pipe writes): `npm run dev:focus` → http://127.0.0.1:5180/

## Specs

- [Focus standalone](../docs/superpowers/specs/2026-09-11-calt-focus-standalone-productivity-design.md)
- [Data split](../docs/superpowers/specs/2026-09-11-productivity-data-split-design.md)
- [Bible/Journal move](../docs/superpowers/specs/2026-09-11-focus-bible-journal-move-design.md)
- [Landing / smoke](../docs/superpowers/exports/2026-09-11-focus-standalone-landing.md)
- Product lock: [AGENTS.md](../AGENTS.md)
