"""
Check Phase-0 / Phase-1 line detection against persisted handwriting paths_json
(if any), else against synthetic multi-line samples from scripts/experiments/out.

Run: .venv\\Scripts\\python.exe scripts\\experiments\\phase1_real_ink_check.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

OUT = Path(__file__).parent / "out"
TRAINING_GLOBS = [
    ROOT / "data_logs" / "training",
    ROOT / "data" / "logs" / "training",
]


def _find_real_paths() -> list[Path]:
    found: list[Path] = []
    for d in TRAINING_GLOBS:
        if d.is_dir():
            found.extend(sorted(d.glob("*.paths.json"))[:20])
    return found


def _synthetic_multi() -> Image.Image:
    img = Image.new("RGB", (320, 220), "white")
    d = ImageDraw.Draw(img)
    d.text((20, 30), "2x + 3 = 7", fill="black")
    d.text((20, 100), "2x = 4", fill="black")
    d.text((20, 170), "x = 2", fill="black")
    return img


def main() -> None:
    from backend.math.line_detect import detect_line_bands, split_lines_projection
    from backend.math.ocr_service import synthesize_from_paths

    report: dict = {"real_paths": 0, "synthetic": {}, "notes": []}

    real = _find_real_paths()
    report["real_paths"] = len(real)
    if real:
        samples = []
        for p in real[:5]:
            try:
                paths = json.loads(p.read_text(encoding="utf-8"))
            except Exception as e:
                samples.append({"path": str(p), "error": str(e)})
                continue
            img = synthesize_from_paths(json.dumps(paths), (800, 600))
            if img is None:
                samples.append({"path": str(p), "error": "no_ink"})
                continue
            bands = split_lines_projection(img)
            samples.append(
                {
                    "path": str(p),
                    "n_bands": len(bands),
                    "bands": [b.as_bbox() for b in bands],
                }
            )
        report["real_samples"] = samples
        report["notes"].append("Ran projection split on persisted paths_json.")
    else:
        report["notes"].append(
            "No *.paths.json under data_logs/training — using synthetic multi-line image."
        )

    # Always run synthetic check (mirrors Phase 0).
    img = _synthetic_multi()
    # Also try Phase 0 samples if present.
    manifest = OUT / "manifest.json"
    if manifest.exists():
        meta = json.loads(manifest.read_text(encoding="utf-8"))
        syn = {}
        for name, info in meta.items():
            if not name.startswith("multi_"):
                continue
            p = OUT / name
            if not p.exists():
                continue
            im = Image.open(p)
            bands = split_lines_projection(im)
            expected = len(info.get("lines") or [])
            syn[name] = {
                "expected": expected,
                "detected": len(bands),
                "ok": len(bands) == expected,
            }
        report["synthetic"] = syn
    else:
        bands = detect_line_bands(img, None)
        report["synthetic"] = {
            "inline_three_lines": {
                "detected": len(bands),
                "ok": len(bands) >= 2,
            }
        }

    OUT.mkdir(parents=True, exist_ok=True)
    out_path = OUT / "phase1_real_ink_check.json"
    out_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    print(f"Wrote {out_path}")


if __name__ == "__main__":
    main()
