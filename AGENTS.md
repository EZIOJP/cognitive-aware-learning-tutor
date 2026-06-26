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

## Cursor Cloud specific instructions

The cloud VM is **Linux** — the `.bat` scripts above are Windows-only. Use the `.sh` scripts or direct commands. The startup update script already creates `.venv` and installs backend + frontend deps; you only need to start services.

- **Backend** (`:8000`): `source .venv/bin/activate && python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload`. On startup it auto-runs Alembic migrations and seeds 192 words into SQLite at `data/vocab_app.db` — no manual migrate/seed step needed.
- **Frontend** (`:5173`): `npm run dev`. Vite proxies `/api` → `http://127.0.0.1:8000`, so the backend must be running for persistent (signed-in) progress.
- **Auth:** `DEV_MODE=true` (from `.env.example`) auto-authenticates, so the UI loads straight to the Study Hub without a login. Default account is `admin` / `admin123`. The GRE Vocab feature is at `/gre-vocab` (the sidebar nav may not route to it; use the URL).
- **Tests:** `.venv/bin/python -m pytest -q`. ~153 pass. 5 failures are expected unless `backend/requirements-notes.txt` is installed (pulls `markdown` + sentence-transformers/PyTorch): they cover transcript-notes/corpus + one math-tutor bank test, all outside the Phase 1 vocab scope.
- **Lint/typecheck:** none configured (no ESLint or `tsconfig.json`; Vite uses esbuild without type-checking). The closest check is `npm run build` (a production build).
