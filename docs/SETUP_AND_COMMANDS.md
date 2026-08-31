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

Optional: [Ollama](https://ollama.com), ESP32 hardware, webcam (focus mirror), SelfTracker on **Microsoft Edge** (`selftracker-extension/`).

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
| **Update / restart after edits** | `scripts\update_and_restart.bat` (menu: tracker / stack / API / extensions / full) | — |
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

This PC is the owner: open the frontend and use **Profile** for display name. Optional admin password (`admin` / `admin123`) remains for lock/import only — not first-run.

**Tailscale (phone / other PC):** same tailnet, stack running. Whole site: `http://<tailscale-100.x>:5173` (Profile shows the live link). API for Android/watch: `:8000`. Allow Windows Firewall for 5173 + 8000 if the page does not load.

---

## Optional components

| Component | Install | Run |
|-----------|---------|-----|
| **Math OCR** (pix2tex) | `scripts\install_ocr.bat` or `./scripts/install_ocr.sh` | `/math-tutor/recognize-test` |
| **Focus mirror** | in core `requirements.txt` (opencv + mediapipe) | `scripts\run_face_tracker.bat` |
| **Ollama LLM** | [ollama.com](https://ollama.com) + set `OLLAMA_ENABLED=1` in `.env` | `ollama pull llama3.2` |
| **Huey LLM jobs** | `pip install huey` (in `backend/requirements.txt`) | **Required for “Test all route profiles”.** In a separate terminal: `python -m backend.core.llm_jobs_worker`. Without it, jobs stay `queued`/`pending` forever in `data/llm_jobs/`. Single-tier “Test chain” does **not** need Huey. |
| **EEG hardware** | `EEG_ENABLED=1` in `.env` | `scripts\run_eeg.bat` (prototype) or main API |
| **SelfTracker (Edge)** | Load unpacked `selftracker-extension/` (v1.5.3+) — or `scripts\launch_selftracker_edge.bat` | After code updates: **Reload** on `edge://extensions`. Fail-closed watch block; `browser.mode` bible/planning/study force-blocks YouTube. API :8000. Edge-only (Zen/Firefox support removed). |
| **Desktop tracker persistence** | `scripts\install_tracker_persistence.bat` | Startup shortcut + logon task + keepalive (~5 min) + HKCU Run. Tray **Confirm exit…** and stop/restart/uninstall bats need `TRACKER_EXIT_PIN` or phrase `I AM DONE TRACKING`. Prefer `scripts\admin_only\stop_desktop_tracker.bat` / `restart_desktop_tracker.bat`. Legitimate uninstall: `scripts\uninstall_tracker_persistence.bat` (set `TRACKER_PERSIST_PROTECT=0` first if Protect rewrites Run). Not AppLocker / not Task Manager disable |
| **CALT Desktop (PySide6)** | `pip install PySide6` (in `backend/requirements.txt`) | **Preferred:** `scripts\desktop_tracker\run_calt_desktop.bat` or `run_desktop_tracker.bat` (now launches Desktop). Autostart/keepalive use the same VBS. Legacy pystray: `set CALT_USE_LEGACY_TRAY=1`. Spec: `docs/superpowers/specs/2026-08-31-calt-desktop-pyside6-design.md` |
| **Voice agent** | Runs inside desktop tracker | Tray → **Voice agent (chat)** · hotkey `Ctrl+Shift+Space` · TTS: `edge-tts` (`en-GB-RyanNeural`) → Piper → SAPI · `pip install edge-tts` · needs LM Studio/Ollama via AI handler |

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
