"""
Phase 0 Experiment 3 — naive horizontal projection-profile line segmentation
+ per-line TexTeller OCR vs whole-image OCR.

Run: .venv\\Scripts\\python.exe scripts\\experiments\\phase0_exp3_segment.py
Requires samples from phase0_make_samples.py.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

OUT = Path(__file__).parent / "out"


def split_lines(img: Image.Image, min_gap_rows: int = 8, pad: int = 10) -> list[tuple[int, int]]:
    """
    Horizontal projection profile: binarize, sum ink per row, split on
    runs of >= min_gap_rows empty rows. Returns (y0, y1) bands.
    """
    gray = np.array(img.convert("L"))
    _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    row_ink = binary.sum(axis=1)
    has_ink = row_ink > 0

    bands: list[tuple[int, int]] = []
    start = None
    gap = 0
    for y, ink in enumerate(has_ink):
        if ink:
            if start is None:
                start = y
            gap = 0
        elif start is not None:
            gap += 1
            if gap >= min_gap_rows:
                bands.append((start, y - gap + 1))
                start = None
                gap = 0
    if start is not None:
        bands.append((start, len(has_ink)))

    h = gray.shape[0]
    return [(max(0, y0 - pad), min(h, y1 + pad)) for y0, y1 in bands]


def main() -> None:
    from backend.math.texteller_onnx import recognize_image

    manifest = json.loads((OUT / "manifest.json").read_text())
    results = {}

    for name, meta in manifest.items():
        if not name.startswith("multi_"):
            continue
        img = Image.open(OUT / name)
        expected = meta["lines"]

        t0 = time.perf_counter()
        bands = split_lines(img)
        seg_ms = (time.perf_counter() - t0) * 1000

        line_results = []
        for i, (y0, y1) in enumerate(bands):
            crop = img.crop((0, y0, img.width, y1))
            crop.save(OUT / f"{name.removesuffix('.png')}_line{i}.png")
            t0 = time.perf_counter()
            latex = recognize_image(crop)
            line_results.append(
                {"band": [y0, y1], "latex": latex, "ocr_s": round(time.perf_counter() - t0, 2)}
            )

        t0 = time.perf_counter()
        whole = recognize_image(img, max_new_tokens=256)
        whole_s = round(time.perf_counter() - t0, 2)

        results[name] = {
            "expected_lines": expected,
            "n_expected": len(expected),
            "n_detected": len(bands),
            "split_correct": len(bands) == len(expected),
            "segmentation_ms": round(seg_ms, 1),
            "per_line": line_results,
            "whole_image_latex": whole,
            "whole_image_ocr_s": whole_s,
        }
        print(f"{name}: expected {len(expected)} lines, detected {len(bands)}")

    (OUT / "exp3_results.json").write_text(json.dumps(results, indent=2))
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
