#!/usr/bin/env bash
# Full dependency install — Linux/macOS. Run from repo root via ./scripts/setup.sh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

PY="${PY:-python3}"
if ! command -v "$PY" &>/dev/null; then
  echo "ERROR: python3 not found. Install Python 3.10–3.12."
  exit 1
fi

echo "[setup] Python: $($PY --version)"

if [[ ! -d "$ROOT/.venv" ]]; then
  echo "[setup] Creating .venv ..."
  "$PY" -m venv "$ROOT/.venv"
fi

# shellcheck source=/dev/null
source "$ROOT/.venv/bin/activate"
pip install -U pip
pip install -r "$ROOT/backend/requirements.txt"
pip install -r "$ROOT/backend/requirements-notes.txt"

echo "[setup] alembic upgrade head"
python -m alembic upgrade head

if [[ ! -d "$ROOT/node_modules" ]]; then
  echo "[setup] npm install ..."
  npm install --no-fund --no-audit
else
  echo "[setup] node_modules present — run 'npm install' manually if package.json changed"
fi

mkdir -p "$ROOT/data" "$ROOT/data_logs"
touch "$ROOT/.venv/.deps-installed"

if [[ ! -f "$ROOT/.env" ]]; then
  cp "$ROOT/.env.example" "$ROOT/.env"
  echo "[setup] Created .env from .env.example"
fi

echo ""
echo "Setup complete."
echo "  API:       python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload"
echo "  Frontend:  npm run dev"
echo "  Or:        ./scripts/run_all.sh"
