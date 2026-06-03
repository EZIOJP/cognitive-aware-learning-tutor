# API contract

Base URL: `http://localhost:8000`  
OpenAPI: `/openapi.json`  
Health: `GET /health`

## Hub (`/api/hub`)

| Method | Path | Notes |
|--------|------|-------|
| POST | `/readings` | Batch ingest |
| POST | `/readings/single` | One reading |
| GET | `/readings` | `slug`, `from`, `to`, `limit` |
| POST | `/sessions` | Start activity session |
| PATCH | `/sessions/{id}` | End / metadata |
| GET | `/daily/{date}` | Life Clock payload (`today` or `YYYY-MM-DD`) |
| POST | `/daily/rebuild` | Recompute rollup |
| GET | `/export` | JSON or `?format=csv` |
| GET/PUT | `/plugins` | User plugin toggles |

### `GET /api/hub/daily/today` (example)

```json
{
  "date": "2026-06-02",
  "segments": [
    { "label": "Sleep", "startHour": 0, "endHour": 7.5, "color": "#6366f1", "type": "sleep" }
  ],
  "productive_minutes": 120,
  "sleep_minutes": 450,
  "life_score": 72,
  "time_left_hours": 8.2,
  "percent_elapsed": 65.8,
  "current_hour": 15.7,
  "stats": { "life_score": 72, "math_attempts": 3, "vocab_events": 5 }
}
```

## Life (`/api/life`)

| Method | Path | Notes |
|--------|------|-------|
| GET | `/daily/{date}` | Read log |
| PUT | `/daily/{date}` | Upsert; returns `life_score` + rollup |

## Insights (`/api/insights`)

| Method | Path | Notes |
|--------|------|-------|
| GET | `/daily` | Structured dashboard inputs |
| POST | `/review` | Heuristic review JSON (Ollama optional later) |

## Math question bank (`/api/math`)

| Method | Path | Notes |
|--------|------|-------|
| POST | `/questions/import/json` | Admin — draft format in `docs/MATH_QUESTION_IMPORT.md` |
| POST | `/questions/import/file` | Admin — JSON file upload |
| POST | `/questions/import/preview` | Admin — validate only |
| GET | `/questions/export/json` | Admin — `?topic=` |
| GET | `/questions` | List bank (no answers) |

Practice: `/api/vocab/math/practice/next` uses bank randomizer, then templates.

## Vocab (`/api/vocab`)

Existing paths preserved: auth, quiz adaptive, words CRUD, progress, math templates/practice, face status, admin.

| Method | Path | Notes |
|--------|------|-------|
| GET | `/words/export/group/{n}` | Full group JSON; `?include_progress=true` |
| GET | `/words/export/group/{n}/csv` | Admin — group CSV export |

Auth: Bearer JWT or demo user when no token.

## Behavior

| Method | Path |
|--------|------|
| WS | `/ws/behavior` |
| GET | `/api/behavior/stats` |

## Errors

HTTP 4xx/5xx with `{"detail": "..."}` (FastAPI default). Validate reading slugs against `reading_definitions`.
