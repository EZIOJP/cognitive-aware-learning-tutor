# Setup, Dependencies, and Commands

This document lists the libraries, commands, and Windows batch files used by the
project.

## System Requirements

- Windows 10/11
- Node.js 20 or newer recommended
- npm
- Python 3.10 or newer recommended
- Optional: Ollama for local LLaVA vision models
- Optional: ESP32-S3 hardware for future real EEG data

## Frontend Dependencies

Installed from `package.json`.

Core:

- `vite`
- `react`
- `react-dom`
- `react-router`
- `react-router-dom`
- `typescript-style TSX through Vite`

UI and styling:

- `tailwindcss`
- `@tailwindcss/vite`
- `@radix-ui/*`
- `lucide-react`
- `class-variance-authority`
- `clsx`
- `tailwind-merge`
- `tw-animate-css`
- `next-themes`
- `@mui/material`
- `@mui/icons-material`
- `@emotion/react`
- `@emotion/styled`

Study UI:

- `react-sketch-canvas`
- `recharts`
- `canvas-confetti`
- `motion`
- `date-fns`

Form and interaction helpers:

- `react-hook-form`
- `cmdk`
- `input-otp`
- `react-day-picker`
- `react-dnd`
- `react-dnd-html5-backend`
- `react-popper`
- `@popperjs/core`
- `react-resizable-panels`
- `react-responsive-masonry`
- `react-slick`
- `embla-carousel-react`
- `sonner`
- `vaul`

## Backend Dependencies

Backend dependencies are listed in:

```text
backend/requirements.txt
```

Current backend requirements:

- `fastapi`
- `uvicorn`
- `websockets`
- `numpy`
- `scipy`
- `pillow`
- `pydantic`

Future optional requirements:

- `opencv-python`
- `mediapipe`
- `ollama`

## Install (automatic)

Double-click **`run.bat`** at the project root. On the **first run** it creates `.venv`, runs `pip install`, and `npm install`. Later runs skip install unless those folders are missing.

To **force refresh** after dependency changes:

```bat
scripts\setup.bat
```

Manual install (optional):

```bat
python -m venv .venv
.venv\Scripts\pip install -r backend\requirements.txt
npm.cmd install
```

Use `npm.cmd` on Windows to avoid PowerShell execution-policy issues.

## Run Frontend

```bat
npm.cmd run dev
```

or:

```bat
scripts\run_frontend.bat
```

Default URL:

```text
http://localhost:5173
```

## Build Frontend

```bat
npm.cmd run build
```

or:

```bat
scripts\build.bat
```

Build output:

```text
dist/
```

## Run Vocab Backend

```bat
scripts\run_backend.bat
```

Default URL:

```text
http://localhost:8000/api/vocab
```

## Run Frontend and Backend Together

```bat
run.bat
```

Installs deps once if needed, then opens the vocab API and frontend in separate windows.

## Optional: EEG Reference Backend

```bat
scripts\run_eeg.bat
```

Default URLs:

```text
http://localhost:8000/health
ws://localhost:8000/ws/eeg
```

## Useful Files

```text
README.md
docs/CURRENT_ARCHITECTURE.md
docs/FUTURE_VISION.md
docs/SETUP_AND_COMMANDS.md
backend/main.py
docs/DATABASE.md
docs/API_CONTRACT.md
docs/CENTRAL_HUB.md
backend/backend_example.py
assets/esp32_firmware_example.cpp
run.bat
scripts/
src/config.ts
```

## Important Config Flags

```ts
config.dev.useSimulatedData = true
config.intervention.enabled = false
config.intervention.autoTrigger = false
```

Change these later when connecting the real FastAPI WebSocket stream and AI
intervention flow.

