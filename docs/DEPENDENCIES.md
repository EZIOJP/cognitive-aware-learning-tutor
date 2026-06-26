# Dependencies & fresh-machine install

**Start here** when cloning on a new Windows, Linux, or macOS machine. Goal: zero surprise missing packages.

Related: [SETUP_AND_COMMANDS.md](./SETUP_AND_COMMANDS.md) · [TROUBLESHOOTING.md](./TROUBLESHOOTING.md) · [MIGRATIONS.md](./MIGRATIONS.md) · [.env.example](../.env.example)

---

## 1. System prerequisites

| Requirement | Version | Notes |
|-------------|---------|--------|
| **Git** | any recent | Clone the repo |
| **Python** | **3.10 – 3.12** (3.11 ideal) | 3.13+ may break `pix2tex` / some wheels on Windows |
| **Node.js** | **20 LTS+** | Includes `npm` |
| **Chrome or Edge** | recent | SelfTracker extension (optional) |
| **Webcam** | optional | Python focus mirror only |

### OS-specific system packages (usually auto via pip)

| Package | Used for | Windows | Linux (Debian/Ubuntu) | macOS |
|---------|----------|---------|------------------------|-------|
| OpenCV | OCR crop, face mirror | via `opencv-python` pip wheel | `libgl1` if import fails | Xcode CLT; pip wheel usually enough |
| Build tools | rare pip builds | [VS Build Tools](https://visualstudio.microsoft.com/visual-cpp-build-tools/) only if OCR install fails | `build-essential python3-dev` | Xcode CLT |

**Headless Linux server (API only, no GUI):** use `opencv-python-headless` instead of `opencv-python` in a local override (see §4).

---

## 2. One-command install

### Windows

```bat
run.bat
```

First run: creates `.venv`, `pip install`, `npm install`, `alembic upgrade head`, starts API + frontend.

Force refresh after `git pull` or dependency changes:

```bat
scripts\setup.bat
```

### Linux / macOS

```bash
chmod +x scripts/setup.sh scripts/run_all.sh scripts/migrate.sh scripts/install_ocr.sh
./scripts/setup.sh
./scripts/run_all.sh
```

---

## 3. Manual install (all platforms)

```bash
# From repo root
python3 -m venv .venv

# Windows
.venv\Scripts\activate
# Linux/macOS
source .venv/bin/activate

pip install -U pip
pip install -r backend/requirements.txt
python -m alembic upgrade head

npm install --no-fund --no-audit
npm run build    # verify frontend
pytest tests/ -q # optional smoke tests
```

Copy environment file:

```bash
cp .env.example .env
# Edit JWT_SECRET before any shared/network deploy
```

---

## 4. Python dependency tiers

### Tier A — Core (required) — `backend/requirements.txt`

| Package | Purpose |
|---------|---------|
| `fastapi`, `uvicorn[standard]` | API server |
| `websockets` | EEG, behavior, NutriNode WS |
| `sqlalchemy`, `alembic` | Database + migrations |
| `pydantic`, `pydantic-settings` | Config + validation |
| `python-jose[cryptography]`, `passlib[bcrypt]`, `bcrypt` | Auth |
| `python-multipart` | CSV upload (admin) |
| `numpy`, `scipy` | EEG FFT, stats |
| `pillow` | Images (OCR decode, face) |
| `sympy` | Math OCR LaTeX validation |
| `opencv-python` | OCR preprocessing, face mirror |
| `mediapipe` | Python focus mirror (`face_tracker.py`) |
| `httpx`, `requests` | Ollama HTTP |
| `pytest` | Tests |

Install:

```bash
pip install -r backend/requirements.txt
```

### Tier B — Math OCR (optional) — `backend/requirements-ocr.txt`

Handwritten math → LaTeX via **pix2tex**. Not required for vocab, hub, or rule-based tutor.

**Windows (recommended):**

```bat
scripts\install_ocr.bat
```

**Linux / macOS:**

```bash
./scripts/install_ocr.sh
```

**Manual (all platforms):**

```bash
pip install pix2tex==0.1.4 --no-deps
pip install -r backend/requirements-ocr.txt
python -c "from pix2tex.cli import LatexOCR; print('OK')"
```

Requires **PyTorch** (large download). GPU optional; CPU works but slower.

Test UI: `/math-tutor/recognize-test` · API: `POST /api/math/ocr`

### Tier C — Local LLM (optional)

**Ollama** — install [Ollama](https://ollama.com) separately (not pip).

```env
OLLAMA_ENABLED=1
OLLAMA_URL=http://127.0.0.1:11434
OLLAMA_MODEL=llama3.2
# OLLAMA_VISION_MODEL=llava   # only if you want vision hints
```

**LM Studio** (native v1 API — recommended for Gemma 4 E4B):

```env
OLLAMA_ENABLED=1
LLM_PROVIDER=lmstudio
OLLAMA_URL=http://127.0.0.1:1234
OLLAMA_MODEL=google/gemma-4-e4b
LLM_MAX_TOKENS=8192
```

Uses `POST /api/v1/chat` with `model` + `input`. Load the model in LM Studio and turn on **Local Server** (default port 1234).

OpenAI-compatible mode (`LLM_PROVIDER=openai`) still works via `/v1/chat/completions` if needed.

Pull models after Ollama install:

```bash
ollama pull llama3.2
# ollama pull llava
# ollama pull qwen2.5:7b   # lecture notes (transcript → markdown)
```

**Primary lecture pipeline:** `transcript-notes-studio\run.bat` (Capture → Tune → Generate). See [docs/TRANSCRIPT_STUDIO_WORKFLOW.md](./TRANSCRIPT_STUDIO_WORKFLOW.md).

**Lecture notes:** set `OLLAMA_ENABLED=1`, use Transcript Notes Studio for capture/generation, then open **Study Library** in the app (`/lecture-notes`) for reading, mermaid repair, and quiz. Legacy: `scripts/run_live_captions_scraper.bat` + `scripts/run_transcript_to_notes.bat --latest`.

Semantic chunking and LLM prompt cache need **sentence-transformers** (pulls PyTorch — large one-time download):

```bat
scripts\install_notes.bat
```

`scripts\run_transcript_to_notes.bat` and `transcript-notes-studio\run.bat` also auto-install `backend/requirements-notes.txt` / `requirements.txt` before each run.

### Tier D — Hardware (optional)

| Component | Software | Doc |
|-----------|----------|-----|
| ESP32 EEG | `EEG_ENABLED=1`, UDP :5005 | [firmware/EEG_ESP32.md](./firmware/EEG_ESP32.md) |
| Focus mirror | `scripts/run_face_tracker.bat` or `python backend/face_tracker.py` | needs webcam + mediapipe |
| NutriNode live | NutriNode plugin + WS | [firmware/NUTRI_ESP32.md](./firmware/NUTRI_ESP32.md) |

---

## 5. Node.js / frontend

Install from `package.json` + `package-lock.json` (use **npm**, not yarn, unless you know what you're doing).

```bash
npm install
npm run dev      # http://localhost:5173
npm run build    # production bundle → dist/
```

Key runtime deps: `react`, `react-dom`, `react-router`, `vite`, `tailwindcss`, `react-sketch-canvas`, `recharts`, `@radix-ui/*`.

Optional dev (Stitch design scripts):

```bash
npm run stitch:verify   # needs STITCH_API_KEY in env for generate
```

---

## 6. Environment variables

Copy [.env.example](../.env.example) → `.env`.

| Variable | Default | Purpose |
|----------|---------|---------|
| `JWT_SECRET` | change in prod | Auth tokens |
| `DEV_MODE` | `true` | Relaxed migration checks |
| `APP_ENV` | `development` | Logging label |
| `CORS_ORIGINS` | `*` | Browser API access |
| `DATABASE_URL` | `sqlite:///.../data/vocab_app.db` | SQLite path |
| `EEG_ENABLED` | `0` | Real UDP EEG service |
| `OLLAMA_ENABLED` | `0` | Call Ollama for math hints |
| `OLLAMA_URL` | `http://127.0.0.1:11434` | Ollama API |
| `OLLAMA_MODEL` | `llama3.2` | Text model |
| `OLLAMA_VISION_MODEL` | empty | Whiteboard vision |
| `FACE_TRACKER_TOKEN` | empty | JWT for hub sync from Python mirror |
| `SEED_WORDS_ON_STARTUP` | `true` | Import `words.json` if DB empty |
| `WORDS_SOURCE` | `auto` | `auto` \| `db` \| `json` |

### Frontend (optional `.env` or `.env.local`)

Vite only exposes `VITE_*` vars.

| Variable | Default | Purpose |
|----------|---------|---------|
| `VITE_API_BASE` | `http://localhost:8000` | Hub, behavior, face APIs |
| `VITE_VOCAB_API_BASE` | `http://localhost:8000/api/vocab` | Auth + vocab |

Example if API runs on another host:

```env
VITE_API_BASE=http://192.168.1.10:8000
VITE_VOCAB_API_BASE=http://192.168.1.10:8000/api/vocab
```

---

## 7. Database & migrations

Canonical DB path: **`data/vocab_app.db`** (legacy root `vocab_app.db` still supported).

```bash
python -m alembic upgrade head
python -m alembic current   # should match head
```

Revisions through **`0006_user_features`**. See [MIGRATIONS.md](./MIGRATIONS.md).

**Do not commit** `vocab_app.db` — each machine gets its own DB from migrations + seed.

---

## 8. Chrome extension (optional)

1. Start API (`run.bat` or `./scripts/run_all.sh`).
2. Chrome → `chrome://extensions` → Developer mode → **Load unpacked**.
3. Select folder: `selftracker-extension/`.
4. Sign in to the app; Life Tracker widget reads `GET /api/behavior/stats`.

Extension connects to `ws://localhost:8000/ws/behavior`.

---

## 9. Ports & URLs

| Service | URL |
|---------|-----|
| Frontend (Vite) | http://localhost:5173 |
| API | http://localhost:8000 |
| Health | http://localhost:8000/health |
| OpenAPI | http://localhost:8000/openapi.json |
| EEG WebSocket | ws://localhost:8000/ws/eeg |
| Behavior WebSocket | ws://localhost:8000/ws/behavior |
| EEG UDP (hardware) | UDP :5005 |

Default login (dev): **admin** / **admin123**

---

## 10. Docker (API only)

```bash
cp .env.example .env
docker compose up --build
```

Frontend still runs via `npm run dev` or static `dist/`. See [DOCKER.md](./DOCKER.md).

---

## 11. Fresh-clone verification checklist

Run on the new machine after install:

```bash
# 1. Backend health
curl http://localhost:8000/health
# expect schema_ok: true

# 2. Frontend build
npm run build

# 3. Tests (optional)
python -m pytest tests/ -q

# 4. OCR (only if Tier B installed)
curl -X POST http://localhost:8000/api/math/ocr -H "Authorization: Bearer TOKEN" ...
# or open /math-tutor/recognize-test in browser after login
```

---

## 12. Common failure → fix

| Symptom | Fix |
|---------|-----|
| `ModuleNotFoundError: backend` | Run uvicorn from **repo root**: `python -m uvicorn backend.main:app` |
| `schema_ok: false` | `python -m alembic upgrade head` |
| `pip install` mediapipe fails | Use Python 3.10–3.12; on Linux try `pip install mediapipe==0.10.14` |
| `npm` execution policy (Windows) | Use `npm.cmd` not `npm` in PowerShell |
| Port 8000 in use | Kill other process or `--port 8001` and update `VITE_*` |
| OCR `pix2tex` import error | Run `scripts/install_ocr.bat` or `./scripts/install_ocr.sh` |
| Face tracker no camera | Close other apps using webcam; run from repo root |
| Extension no data | API running + reload extension + sign in |
| CORS errors | Set `CORS_ORIGINS=*` or your frontend origin in `.env` |
| Blank vocab / no words | `SEED_WORDS_ON_STARTUP=true`; ensure `public/data/words.json` exists |

More: [TROUBLESHOOTING.md](./TROUBLESHOOTING.md)

---

## 13. Files reference

| File | Role |
|------|------|
| `backend/requirements.txt` | Core Python |
| `backend/requirements-ocr.txt` | pix2tex stack |
| `package.json` / `package-lock.json` | Frontend |
| `.env.example` | Env template |
| `scripts/_common.bat` | Windows bootstrap |
| `scripts/setup.sh` | Linux/macOS bootstrap |
| `alembic/` | DB migrations |
| `assets/face_landmarker.task` | Auto-downloaded by face tracker if missing |
