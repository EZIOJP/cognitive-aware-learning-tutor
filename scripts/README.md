# Scripts

Windows batch helpers. All scripts `cd` to the project root via `_common.bat`.

## Daily use

| Script | Purpose |
|--------|---------|
| **`run.bat`** (project root) | Install deps **once** if missing, then start vocab API + frontend |
| `run_all.bat` | Same as `run.bat` (called by root launcher) |
| `run_backend.bat` | Vocab FastAPI only (`backend/vocab_backend.py`) |
| `run_frontend.bat` | Vite dev server only |

First run creates `.venv`, runs `pip install`, and `npm install`. Later runs skip install unless folders are missing.

## Setup / build

| Script | Purpose |
|--------|---------|
| `setup.bat` | Force refresh deps after `requirements.txt` or `package.json` changes |
| `build.bat` | Production build → `dist/` |

## Optional tools

| Script | Purpose |
|--------|---------|
| `run_eeg.bat` | EEG WebSocket prototype (`backend/backend_example.py`) — not the main app API |
| `run_face_tracker.bat` | Face landmark tracker |
| `launch_selftracker_chrome.bat` | Chrome + SelfTracker extension |
| `launch_selftracker_edge.bat` | Edge + SelfTracker extension |

## URLs

- Frontend: `http://localhost:5173`
- Vocab API: `http://localhost:8000/api/vocab`

## Removed (consolidated)

- `run_vocab_backend.bat` → use `run_backend.bat`
- `run_mock_stack.bat` → use `run.bat` / `run_all.bat`
- `build_app.bat` → use `build.bat`
