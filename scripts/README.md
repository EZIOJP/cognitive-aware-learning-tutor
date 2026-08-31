# Scripts

Launch helpers for Windows (`.bat`) and Linux/macOS (`.sh`). All scripts run from the **repo root**.

**Full install guide:** [docs/DEPENDENCIES.md](../docs/DEPENDENCIES.md)

---

## Daily use

| Script | Platform | Purpose |
|--------|----------|---------|
| **`run.bat`** (repo root) | Windows | Install deps if missing, migrate, start API + frontend |
| **`update_and_restart.bat`** | Windows | After code changes: tracker only / stack only / API / extensions / full |
| `run_all.bat` | Windows | Same (called by `run.bat`) |
| `run_all.sh` | Linux/macOS | Migrate + API + frontend |
| `run_backend.bat` | Windows | API only (`backend.main:app`) |
| `run_frontend.bat` | Windows | Vite dev server |
| `device_block_apply.bat` | Windows (admin) | Device-wide porn/YouTube block via hosts file (all apps) |
| `device_block_remove.bat` | Windows (admin) | Remove CALT hosts block |

### Linux/macOS first-time setup

```bash
chmod +x scripts/setup.sh scripts/run_all.sh scripts/migrate.sh scripts/install_ocr.sh
./scripts/setup.sh
./scripts/run_all.sh
```

---

## Setup / build

| Script | Platform | Purpose |
|--------|----------|---------|
| `setup.bat` | Windows | Force `pip` + `npm` refresh |
| `setup.sh` | Linux/macOS | Create `.venv`, install deps, migrate, copy `.env` |
| `build.bat` | Windows | `npm run build` → `dist/` |
| `migrate.bat` / `migrate.sh` | Both | `alembic upgrade head` |

---

## Optional tools

| Script | Purpose |
|--------|---------|
| `install_ocr.bat` / `install_ocr.sh` | pix2tex math OCR (large PyTorch download) |
| `install_notes.bat` / `install_notes.sh` | Lecture-notes semantic embeddings (`sentence-transformers`) |
| `run_live_captions_scraper.bat` | **Legacy** — delegates to `transcript-notes-studio` CLI `capture` |
| `run_transcript_to_notes.bat` | **Legacy** — delegates to `transcript-notes-studio` CLI `generate` |
| `run_face_tracker.bat` | Python webcam focus mirror → hub |
| `run_eeg.bat` | Legacy EEG prototype (`backend_example.py`) — use main API for integrated stack |
| `launch_selftracker_chrome.bat` | Chrome + SelfTracker (legacy helper; prefer Edge) |
| `launch_selftracker_edge.bat` | Edge + SelfTracker (supported browser gate) |

---

## URLs

- Frontend: http://localhost:5173
- API: http://localhost:8000/health
- Login: **admin** / **admin123**

---

## Shared Windows bootstrap

`_common.bat` sets `ROOT`, activates `.venv`, and ensures deps are installed. Used by all `.bat` scripts.
