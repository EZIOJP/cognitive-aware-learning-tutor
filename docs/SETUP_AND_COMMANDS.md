# Setup, Dependencies, and Commands

**Fresh machine?** Start with **[DEPENDENCIES.md](./DEPENDENCIES.md)** — Python/Node versions, optional OCR/Ollama, env vars, ports, and a verification checklist for Windows, Linux, and macOS.

This page is the quick command reference.

---

## System requirements

| | |
|--|--|
| **Python** | 3.10 – 3.12 (3.11 recommended) |
| **Node.js** | 20 LTS+ |
| **OS** | Windows 10/11, Linux, macOS |

Optional: [Ollama](https://ollama.com), ESP32 hardware, webcam (focus mirror), Chrome (SelfTracker extension).

---

## One-command start

### Windows

```bat
run.bat
```

First run: `.venv`, `pip install`, `npm install`, `alembic upgrade head`, then API + frontend.

Force refresh after `git pull` or dependency changes:

```bat
scripts\setup.bat
```

### Linux / macOS

```bash
chmod +x scripts/*.sh
./scripts/setup.sh      # first time or after dep changes
./scripts/run_all.sh    # migrations + API + frontend
```

---

## Manual install

```bash
python3 -m venv .venv

# Windows
.venv\Scripts\activate
# Linux/macOS
source .venv/bin/activate

pip install -U pip
pip install -r backend/requirements.txt
python -m alembic upgrade head

npm install
cp .env.example .env    # if .env missing
```

Windows: use `npm.cmd` if PowerShell blocks `npm`.

---

## Run services

| What | Windows | Linux/macOS |
|------|---------|-------------|
| **Full stack** | `run.bat` | `./scripts/run_all.sh` |
| **API only** | `scripts\run_backend.bat` | `python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload` |
| **Frontend only** | `scripts\run_frontend.bat` | `npm run dev` |
| **Migrations** | `scripts\migrate.bat` | `./scripts/migrate.sh` |
| **Production build** | `scripts\build.bat` | `npm run build` |

### URLs

| Service | URL |
|---------|-----|
| Frontend | http://localhost:5173 |
| API health | http://localhost:8000/health |
| Vocab API | http://localhost:8000/api/vocab |
| OpenAPI | http://localhost:8000/openapi.json |

Default login: **admin** / **admin123**

---

## Optional components

| Component | Install | Run |
|-----------|---------|-----|
| **Math OCR** (pix2tex) | `scripts\install_ocr.bat` or `./scripts/install_ocr.sh` | `/math-tutor/recognize-test` |
| **Focus mirror** | in core `requirements.txt` (opencv + mediapipe) | `scripts\run_face_tracker.bat` |
| **Ollama LLM** | [ollama.com](https://ollama.com) + set `OLLAMA_ENABLED=1` in `.env` | `ollama pull llama3.2` |
| **EEG hardware** | `EEG_ENABLED=1` in `.env` | `scripts\run_eeg.bat` (prototype) or main API |
| **SelfTracker** | Load `selftracker-extension/` in Chrome | API must be on :8000 |

See [DEPENDENCIES.md](./DEPENDENCIES.md) for tiers, env vars, and troubleshooting.

---

## Dependency files

| File | Contents |
|------|----------|
| `backend/requirements.txt` | Core Python (FastAPI, SQLAlchemy, OpenCV, MediaPipe, SymPy, …) |
| `backend/requirements-ocr.txt` | pix2tex + PyTorch (optional) |
| `package.json` / `package-lock.json` | React + Vite frontend |
| `.env.example` | Environment template |

---

## Scripts folder

| Script | Platform | Purpose |
|--------|----------|---------|
| `run.bat` / `run_all.bat` | Windows | Full stack |
| `setup.bat` | Windows | Force reinstall deps |
| `setup.sh` / `run_all.sh` | Unix | Install / run |
| `migrate.bat` / `migrate.sh` | Both | `alembic upgrade head` |
| `install_ocr.bat` / `install_ocr.sh` | Both | Math OCR stack |

Details: [scripts/README.md](../scripts/README.md)

---

## Related docs

- [DEPENDENCIES.md](./DEPENDENCIES.md) — master install guide
- [TROUBLESHOOTING.md](./TROUBLESHOOTING.md) — common errors
- [MIGRATIONS.md](./MIGRATIONS.md) — database upgrades
- [DATABASE.md](./DATABASE.md) — schema and env
- [DOCKER.md](./DOCKER.md) — container API
- [WORKING_PRODUCT.md](./WORKING_PRODUCT.md) — what works without hardware
