#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
source "$ROOT/.venv/bin/activate"
echo "[migrate] alembic upgrade head"
python -m alembic upgrade head
python -m alembic current
