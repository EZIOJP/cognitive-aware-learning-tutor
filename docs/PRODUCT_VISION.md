# Product vision

Cognitive-Aware Learning Tutor is a personal learning OS: vocab, math practice, life habits, nutrition, browser behavior, and optional biosignals feed a **single time-series hub**. The UI is a thin client over documented HTTP APIs.

## Principles

1. **Backend first** — SQLite + Alembic today; PostgreSQL migration path documented.
2. **One database** — progress, life logs, readings, rollups, sessions.
3. **New metric = definition row + writer** — not a new monolith patch.
4. **Life Clock from API** — `GET /api/hub/daily/{date}` drives the 24h ring.
5. **AI for polish later** — after OpenAPI and real JSON exist.

## Phases

| Phase | Focus |
|-------|--------|
| R1–R5 | Backend, hub, migrations, tests, docs |
| F | Frontend from OpenAPI + visual polish |

## Out of scope (for now)

Community features, user-uploaded plugins, hosted Postgres, major FE redesign without API contract.
