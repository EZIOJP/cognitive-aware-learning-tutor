# CALT Focus — Productivity product

Clean top-level home for Focus. Study (GRE / notes / math / `:8000`) stays elsewhere in the repo.

```text
calt-focus/
  frontend/     ← Vite design host + build entry (FE)
  backend/      ← C++ enforcer, Focus shell, msg-host (BE)
  extensions/   ← Gate + SelfTracker browser extensions
```

| Folder | Open first |
|--------|------------|
| [frontend/](./frontend/README.md) | React UI build / design host |
| [backend/](./backend/README.md) | Native SoftLand / Arm / Plan / Bible / Journal |
| [extensions/](./extensions/README.md) | Browser Gate + track |

Shared React sources still live under repo `src/` (Focus shell + Study interstitial share components). FE paths for review are listed in `frontend/README.md`.

## Run

```bat
npm run build:focus
scripts\desktop_tracker\build\build_native_enforcer.bat
scripts\desktop_tracker\build\build_native_focus.bat
scripts\desktop_tracker\build\build_calt_msg_host.bat
scripts\desktop_tracker\run\run_calt_desktop.bat
```

Design host: `npm run dev:focus` → http://127.0.0.1:5180/

## Specs

- [Focus standalone](../docs/superpowers/specs/2026-09-11-calt-focus-standalone-productivity-design.md)
- [Data split](../docs/superpowers/specs/2026-09-11-productivity-data-split-design.md)
- [AGENTS.md](../AGENTS.md)
