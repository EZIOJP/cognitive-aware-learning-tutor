# Database

## Location

SQLite file: `data/vocab_app.db` (see `backend/paths.py`).

## Migrations

**Single authority:** [MIGRATIONS.md](./MIGRATIONS.md) — read this for every upgrade path (fresh clone, legacy DB, new columns, Postgres).

Revision chain:

1. `0001_baseline` — `users`, `word_progress`, `math_question_templates`, `math_attempts`
2. `0002_hub` — hub, life, `quiz_sessions`
3. `0003_math_bank` — `math_questions`, attempt linkage
4. `0004_reconcile` — idempotent repair for legacy / partial DBs
5. `0005_words_hub` — `words` table; `hub_session_id` on quiz + math attempts

```bat
scripts\migrate.bat
rem or: python -m alembic upgrade head
```

`create_all()` is **disabled**; the API refuses to start in production mode if migrations are behind head.

## Environment

| Variable | Default |
|----------|---------|
| `DATABASE_URL` | `sqlite:///.../data/vocab_app.db` |
| `JWT_SECRET` | dev default (set in production) |
| `DEV_MODE` | `true` — migration mismatch logs warning; `false` raises on startup |
| `EXPOSE_PASSWORD_PLAIN` | `true` in dev only; `false` in production |
| `WORDS_SOURCE` | `auto` (DB if seeded, else JSON), `db`, or `json` |
| `SEED_WORDS_ON_STARTUP` | `true` — import `words.json` into DB when `words` is empty |

## PostgreSQL (later)

Set `DATABASE_URL=postgresql+psycopg://...` and run the same Alembic commands.

## Non-DB data

| Data | Storage |
|------|---------|
| Vocab words | `words` table (canonical when seeded); `public/data/words.json` bootstrap + mirror on admin writes |
| Math question bank (imported) | `math_questions` table |
| Seeds (metrics, plugins) | `backend/scripts/seed_definitions.py` + app lifespan |

## Integrity

- User-owned rows cascade on delete
- Timestamps stored UTC; API uses ISO-8601
- Composite index on readings `(user_id, recorded_at)`
