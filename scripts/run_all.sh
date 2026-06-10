#!/usr/bin/env bash
# Start API + frontend — Linux/macOS
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [[ ! -f "$ROOT/.venv/bin/activate" ]]; then
  echo "Run ./scripts/setup.sh first."
  exit 1
fi

# shellcheck source=/dev/null
source "$ROOT/.venv/bin/activate"

echo "Applying database migrations..."
python -m alembic upgrade head

echo ""
echo "Starting Cognitive-Aware Learning Tutor..."
echo "  API (local):   http://localhost:8000/health"
echo "  Frontend:      http://localhost:5173"
echo "  Login:         admin / admin123"
bash "$(dirname "$0")/print_lan_urls.sh"
echo ""

cleanup() {
  echo "Stopping servers..."
  [[ -n "${API_PID:-}" ]] && kill "$API_PID" 2>/dev/null || true
  exit 0
}
trap cleanup INT TERM

python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload &
API_PID=$!

npm run dev
