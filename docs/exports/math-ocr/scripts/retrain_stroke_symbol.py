#!/usr/bin/env python3
"""Retrain stroke_symbol disambiguator from DSC_handwriting_dataset paths_json."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.math.stroke_symbol import train_from_handwriting_dataset  # noqa: E402


def main() -> int:
    p = argparse.ArgumentParser(description="CALT stroke-symbol retrain from real ink")
    p.add_argument("--min-samples", type=int, default=3, help="Minimum real glyph samples required")
    p.add_argument("--synth-per-class", type=int, default=15, help="Synthetic augments per default class")
    p.add_argument("--no-synthetic", action="store_true", help="Real ink only")
    args = p.parse_args()

    result = train_from_handwriting_dataset(
        min_real_samples=args.min_samples,
        include_synthetic=not args.no_synthetic,
        synth_per_class=args.synth_per_class,
    )
    print(json.dumps(result, indent=2))
    return 0 if result.get("status") == "trained" else 1


if __name__ == "__main__":
    raise SystemExit(main())
