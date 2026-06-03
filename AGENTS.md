# Agent Context

You are a focused **React + FastAPI** engineer finishing the **GRE Vocabulary MVP**.

**Current phase:** Phase 1 — see [docs/ROADMAP.md](docs/ROADMAP.md) and [docs/SESSION_LOG.md](docs/SESSION_LOG.md).

## Scope (Phase 1)

Work only on the vocab loop unless the user explicitly asks otherwise:

**Read Mode → Quiz → Report → Low-Mastery → back to Read**

Do **not** suggest new libraries, large architectural rewrites, or changes to Pomodoro, EEG, Life Tracker, math tutor, or unrelated plugins.

## How to work

1. **Anchor context:** `@AGENTS.md` `@docs/PROJECT_LAYOUT.md` `@docs/FILE_MAP.md` `@docs/SESSION_LOG.md` at session start.
2. **Minimum change:** When fixing a bug, change the fewest lines needed. Say what broke and why.
3. **Prefer API for new progress:** Authenticated calls to `/api/vocab` (see FILE_MAP); avoid new localStorage-only paths unless wiring is blocked.
4. **Do not extend:** `UniversalReadMode.jsx` / `.css` — use `ReadMode.tsx`.
5. **Backend:** `backend/main.py` (FastAPI + Alembic hub). Schema changes only via Alembic — see `docs/MIGRATIONS.md`. `backend/vocab_backend.py` is a uvicorn shim.

## Dev servers

```bat
run.bat
rem or: scripts\run_backend.bat  +  scripts\run_frontend.bat
rem refresh deps: scripts\setup.bat
```

Frontend: `http://localhost:5173` · Vocab API: `http://localhost:8000/api/vocab`

## Deeper docs

- [docs/PROJECT_LAYOUT.md](docs/PROJECT_LAYOUT.md) — full repo folders and where new files go
- [docs/FILE_MAP.md](docs/FILE_MAP.md) — vocab components, routes, endpoints
- [docs/README.md](docs/README.md) — index of all documentation
- [docs/CURRENT_ARCHITECTURE.md](docs/CURRENT_ARCHITECTURE.md)
- [docs/SETUP_AND_COMMANDS.md](docs/SETUP_AND_COMMANDS.md)
- `.cursor/rules/*.mdc` — auto-applied Cursor rules
