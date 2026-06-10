#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
[[ -d .venv ]] && source .venv/bin/activate

export TEXTELLER_CACHE_DIR="${TEXTELLER_CACHE_DIR:-$ROOT/models/texteller}"
mkdir -p "$TEXTELLER_CACHE_DIR"

python - <<'PY'
import os
from optimum.onnxruntime import ORTModelForVision2Seq
from transformers import AutoImageProcessor, AutoTokenizer

mid = os.environ.get("TEXTELLER_MODEL_ID", "Ji-Ha/TexTeller3-ONNX-dynamic")
cache = os.environ["TEXTELLER_CACHE_DIR"]
ORTModelForVision2Seq.from_pretrained(mid, provider="CPUExecutionProvider", export=False, cache_dir=cache)
AutoImageProcessor.from_pretrained(mid, cache_dir=cache)
AutoTokenizer.from_pretrained(mid, cache_dir=cache)
print("OK: cached to", cache)
PY
