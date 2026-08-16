"""
Phase 0 Experiment 2b — probe pix2text-mfd-1.5 ONNX directly with onnxruntime.

Downloads the 80MB model from HF (breezedeus/pix2text-mfd-1.5) into the normal
HF cache, opens an ORT session, prints input/output signatures, and runs one
dummy inference to measure raw detect latency. No YOLO postprocessing —
feasibility probe only.

Run: .venv\\Scripts\\python.exe scripts\\experiments\\phase0_exp2_mfd_probe.py
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import numpy as np


def main() -> None:
    from huggingface_hub import hf_hub_download
    import onnxruntime as ort

    t0 = time.perf_counter()
    model_path = hf_hub_download("breezedeus/pix2text-mfd-1.5", "pix2text-mfd-1.5.onnx")
    dl_s = time.perf_counter() - t0

    t0 = time.perf_counter()
    sess = ort.InferenceSession(model_path, providers=["CPUExecutionProvider"])
    load_s = time.perf_counter() - t0

    info = {
        "model_path": model_path,
        "download_or_cache_s": round(dl_s, 1),
        "session_load_s": round(load_s, 2),
        "inputs": [{"name": i.name, "shape": i.shape, "type": i.type} for i in sess.get_inputs()],
        "outputs": [{"name": o.name, "shape": o.shape, "type": o.type} for o in sess.get_outputs()],
    }

    # One dummy inference at a typical YOLO input size to gauge latency.
    inp = sess.get_inputs()[0]
    shape = [d if isinstance(d, int) else (1 if i == 0 else 768) for i, d in enumerate(inp.shape)]
    dummy = np.random.rand(*shape).astype(np.float32)
    times = []
    for _ in range(3):
        t0 = time.perf_counter()
        out = sess.run(None, {inp.name: dummy})
        times.append(time.perf_counter() - t0)
    info["dummy_input_shape"] = shape
    info["output_shapes_actual"] = [list(o.shape) for o in out]
    info["infer_s_runs"] = [round(t, 3) for t in times]

    print(json.dumps(info, indent=2))
    out_file = Path(__file__).parent / "out" / "exp2_mfd_probe.json"
    out_file.write_text(json.dumps(info, indent=2))


if __name__ == "__main__":
    main()
