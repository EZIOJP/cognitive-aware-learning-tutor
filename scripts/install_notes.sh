#!/usr/bin/env bash
# Install lecture-notes semantic embedding deps into project .venv
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [[ ! -d "$ROOT/.venv" ]]; then
  echo "ERROR: .venv missing. Run ./scripts/setup.sh first."
  exit 1
fi

# shellcheck source=/dev/null
source "$ROOT/.venv/bin/activate"
pip install -r "$ROOT/backend/requirements-notes.txt"
python -c "from sentence_transformers import SentenceTransformer; print('OK: sentence-transformers ready')"
