# Central hub

The hub stores **reading definitions** (metric catalog) and **readings** (time-series facts). **Daily rollups** cache Life Clock segments and dashboard stats.

## Tables

- `reading_definitions` — slug, label, unit, `source_type`, `feature_id`, `is_system`
- `readings` — `user_id`, `definition_id`, `recorded_at`, `value_numeric`, `value_json`
- `sessions` — bounded activities (`vocab_quiz`, `math_practice`, etc.)
- `life_daily_log` — one row per user per calendar day
- `daily_rollups` — `segments_json`, productive/sleep minutes, counters
- `user_plugins` — enabled plugins per user (built-in + custom feature ids)
- `user_features` — user-created feature modules (name, metrics, config)
- `reading_definitions.user_id` — custom per-user metric slugs (`u{id}_{slug}`)
- `quiz_sessions` — persistent vocab quiz state

## Writers

| Source | Slug | Trigger |
|--------|------|---------|
| Vocab | `vocab_quiz_complete` | Quiz complete |
| Math | `math_attempt` | Practice submit |
| Face | `face_attention` | Face status POST |
| Life | `sleep_hours`, `study_minutes` | Life daily PUT |
| Behavior WS | `browser_event` | Extension stream |
| Nutrinode | `calories` | Meal logged |

## Rollup

On life daily save or ingest, `hub/services/rollup.py` rebuilds `daily_rollups` for that date. Clients should call `GET /api/hub/daily/{YYYY-MM-DD}` instead of computing rings in React.

## Run

```bat
python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
alembic upgrade head
python -m backend.scripts.seed_definitions
```
