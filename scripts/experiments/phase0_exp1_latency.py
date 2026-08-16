"""
Phase 0 Experiment 1 — TexTeller ONNX latency, default vs tuned session options.

Run each mode in a separate process so ORT global state doesn't leak:
  .venv\\Scripts\\python.exe scripts\\experiments\\phase0_exp1_latency.py default
  .venv\\Scripts\\python.exe scripts\\experiments\\phase0_exp1_latency.py tuned

Tuned = ORT_SEQUENTIAL + intra_op_num_threads=<physical cores> + no spinning
(session.intra_op.allow_spinning=0), per onnxruntime threading guidance.
"""

from __future__ import annotations

import json
import statistics
import sys
import time
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

MODEL_ID = "Ji-Ha/TexTeller3-ONNX-dynamic"
PHYSICAL_CORES = 8
N_RUNS = 10
IMG = Path(__file__).parent / "out" / "single_line.png"


def build_session_options(mode: str):
    if mode == "default":
        return None
    import onnxruntime as ort

    so = ort.SessionOptions()
    so.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
    so.intra_op_num_threads = PHYSICAL_CORES
    so.add_session_config_entry("session.intra_op.allow_spinning", "0")
    return so


def load(mode: str):
    from optimum.onnxruntime import ORTModelForVision2Seq
    from transformers import AutoImageProcessor, AutoTokenizer

    kwargs = {"provider": "CPUExecutionProvider", "export": False}
    so = build_session_options(mode)
    if so is not None:
        kwargs["session_options"] = so
    model = ORTModelForVision2Seq.from_pretrained(MODEL_ID, **kwargs)
    proc = AutoImageProcessor.from_pretrained(MODEL_ID)
    tok = AutoTokenizer.from_pretrained(MODEL_ID)
    return model, proc, tok


def main() -> None:
    mode = sys.argv[1] if len(sys.argv) > 1 else "default"
    from backend.math.texteller_onnx import _pil_to_model_input, strip_latex_delimiters

    t0 = time.perf_counter()
    model, proc, tok = load(mode)
    load_s = time.perf_counter() - t0

    img = Image.open(IMG)
    pixel_values = _pil_to_model_input(img, proc)

    # warmup (excluded from stats)
    t0 = time.perf_counter()
    out = model.generate(pixel_values=pixel_values, max_new_tokens=128)
    warmup_s = time.perf_counter() - t0
    latex = strip_latex_delimiters(tok.batch_decode(out, skip_special_tokens=True)[0])

    times = []
    for _ in range(N_RUNS):
        t0 = time.perf_counter()
        model.generate(pixel_values=pixel_values, max_new_tokens=128)
        times.append(time.perf_counter() - t0)

    times.sort()
    result = {
        "mode": mode,
        "session_options_applied": mode != "default",
        "model_load_s": round(load_s, 2),
        "warmup_s": round(warmup_s, 2),
        "n_runs": N_RUNS,
        "p50_s": round(statistics.median(times), 3),
        "p90_s": round(times[int(0.9 * (len(times) - 1))], 3),
        "min_s": round(times[0], 3),
        "max_s": round(times[-1], 3),
        "sample_latex": latex,
    }
    print(json.dumps(result, indent=2))
    out_file = Path(__file__).parent / "out" / f"exp1_{mode}.json"
    out_file.write_text(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
