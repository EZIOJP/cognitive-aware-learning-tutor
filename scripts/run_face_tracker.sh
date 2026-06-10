#!/usr/bin/env bash
# Python focus mirror — Linux/macOS
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
source "$ROOT/.venv/bin/activate"
exec python "$ROOT/backend/face_tracker.py" "$@"
