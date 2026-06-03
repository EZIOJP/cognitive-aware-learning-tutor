# Database migrations (Alembic)

**Rule:** All schema changes go through Alembic revisions. Models in `backend/models/` must match applied migrations. Do not use `Base.metadata.create_all()` (disabled in `init_db()`).

## Revision chain

| Revision | Purpose |
|----------|---------|
| `0001_baseline` | Core tables; **skips create** if `users` already exists (legacy `create_all` DBs) |
| `0002_hub` | Hub, life log, quiz sessions |
| `0003_math_bank` | `math_questions`; extends `math_attempts` (idempotent checks) |
| `0004_reconcile` | **Idempotent repair** — missing tables/columns, `password_plain`, partial upgrades |
| `0005_words_hub` | `words` table; `hub_session_id` on `quiz_sessions` and `math_attempts` |

## Everyday commands

```bat
python -m alembic upgrade head
python -m alembic current
python -m alembic history
```

`scripts\migrate.bat` — upgrade only.  
`scripts\_common.bat` runs `alembic upgrade head` after pip install.

## Scenarios (every manipulation path)

### 1. Fresh clone (no DB file)

```bat
alembic upgrade head
```

Creates `data/vocab_app.db` and all tables.

### 2. Existing DB from old `create_all` (has data, no `alembic_version`)

```bat
alembic stamp 0001_baseline
alembic upgrade head
```

`0001` will not recreate `users`. `0002`–`0004` add missing schema. `0004` adds `password_plain` if absent.

If unsure which revision matches the file:

```bat
alembic current
```

### 3. Existing DB already on Alembic (normal)

```bat
git pull
alembic upgrade head
```

App startup calls `ensure_at_head()` — warns in dev, **raises in production** (`dev_mode=false`) if behind head.

### 4. Add a new column or table (your job going forward)

1. Edit SQLAlchemy models under `backend/models/`.
2. Ensure model is imported in `backend/models/__init__.py` (needed for autogenerate metadata).
3. Generate revision:

```bat
python -m alembic revision --autogenerate -m "describe_change"
```

4. **Edit the generated file** — use idempotent patterns from `0003` / `0004`:

   - `if not insp.has_table(...): op.create_table(...)`
   - `if column not in cols: batch.add_column(...)`

5. Test:

```bat
alembic upgrade head
alembic downgrade -1
alembic upgrade head
```

6. Never edit applied revisions on machines that already ran them — add `0005_...` instead.

### 5. Data-only changes (seed metrics, plugins)

Use scripts, not Alembic:

- `python -m backend.scripts.seed_definitions`
- App lifespan seeds reading definitions / default admin

### 6. Postgres (later)

Set `DATABASE_URL=postgresql+psycopg://user:pass@host/db`.  
Same commands; remove SQLite-only assumptions in new migrations (prefer portable SQLAlchemy types).

### 7. Backup before risky upgrade

```bat
copy data\vocab_app.db data\vocab_app.db.bak
```

### 8. Stuck / duplicate table errors

Usually means a table exists but Alembic revision is behind. Run:

```bat
alembic upgrade head
```

`0004_reconcile` creates only **missing** objects. If still failing, inspect:

```bat
python -m alembic current
```

and compare to `alembic history`.

### 9. Downgrade

Downgrades are best-effort. `0004` downgrade is a no-op by design. Prefer restore from `.bak` in development.

## What is NOT migrated

| Data | Storage |
|------|---------|
| Vocab word content | `public/data/words.json` (file) |
| Reading definition seed rows | App startup + `seed_definitions` script |
| Behavior CSV logs | `data/logs/` |

Future `words` table will need its own `0005_words_table` revision.

## Helpers

- `backend/db/migration_utils.py` — `has_table`, `add_column_if_missing` for new revisions
- `backend/db/migrate.py` — `ensure_at_head()`, `get_revision_state()`

## Checklist before merging schema work

- [ ] New revision id increments (`0005_...`)
- [ ] Idempotent where upgrading old DBs
- [ ] Model + migration agree
- [ ] `alembic upgrade head` on empty DB
- [ ] `alembic upgrade head` on your existing `vocab_app.db`
- [ ] pytest passes
