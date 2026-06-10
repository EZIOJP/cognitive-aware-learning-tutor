# Docker deployment (API)

Backend-only container for production-like runs. Frontend stays separate (`npm run dev` or static hosting).

## Quick start

```bash
cp .env.example .env
# Edit JWT_SECRET and set EXPOSE_PASSWORD_PLAIN=false

docker compose up --build
```

API: http://localhost:8000 — health at `/health`, OpenAPI at `/openapi.json`.

## Volumes

- `./data` — SQLite database
- `./public/data` — `words.json` bootstrap for first-time seed

## Environment

See `.env.example`. In Compose, `DEV_MODE=false` enforces schema-at-head on startup.

## Without Docker

```bash
python -m alembic upgrade head
python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000
```
