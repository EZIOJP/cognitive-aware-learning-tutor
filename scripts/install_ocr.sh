#!/usr/bin/env bash
# Math OCR (TexTeller ONNX, CPU) — Linux/macOS
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [[ -d .venv ]]; then
  # shellcheck disable=SC1091
  source .venv/bin/activate
fi

echo "Installing TexTeller ONNX stack (CPU only)..."
pip install -r "$ROOT/backend/requirements-ocr.txt"

python -c "from backend.math.texteller_onnx import texteller_available; assert texteller_available(); print('OK: TexTeller ONNX ready')"

echo "Done. Model weights download on first POST /api/math/ocr request."
