# Project Status

Last updated: 2026-06-02

## Current focus

Modular **hub + plugins** platform: users enable modules, add custom features/metrics, and drive a customizable dashboard from central data.

## Working now

- **Core hub**: readings, rollups, life daily log, `GET/PUT /api/hub/dashboard-layout`
- **Plugins** (toggle + server sync): Core Hub, Math Tutor, GRE Vocab, Life Tracker, EEG, Focus Mirror, NutriNode
- **Feature Studio**: create/edit/delete custom features, export JSON/CSV
- **Dashboard**: 24h Life Clock, AI review card, drag/resize layout (local + server when signed in)
- **Behavior extension** → hub `browser_event` + richer stats API
- **Python focus mirror** (`backend/face_tracker.py`) + calibration UI (`/focus/calibrate`)
- **Math tutor hint** — rule-based by default; Ollama only if `OLLAMA_ENABLED=1`
- **EEG**: `GET /ws/eeg` + optional UDP (`EEG_ENABLED=1`, port 5005); frontend uses WS when simulation off
- Vocab, math bank, Docker compose, Alembic through `0006_user_features`

## Run locally

```bat
run.bat
```

(`run.bat` runs migrations automatically.) Daily checklist: **[WORKING_PRODUCT.md](./WORKING_PRODUCT.md)**.

Optional:

```bat
set EEG_ENABLED=1
scripts\run_face_tracker.bat
```

## Prototype login

```text
username: admin
password: admin123
```

## GRE Phase 1 (done)

- Read / cycle / low-mastery use API when signed in; `POST /progress/{id}/read`
- Hub + cycle empty/error states; admin group export — [GRE_VOCAB_PHASE1.md](./GRE_VOCAB_PHASE1.md)

## Next (see docs/ROADMAP.md)

- Phase 2 hardware (ESP32) when boards arrive
- Ollama vision on whiteboard snapshots
- Community module
- User-defined ingest handlers (JS / FastAPI webhooks)
- PostgreSQL + production hardening
