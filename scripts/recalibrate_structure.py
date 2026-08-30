#!/usr/bin/env python3
"""Recalibrate structure_verify thresholds from handwriting dataset + fixtures."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.math.structure_calibrate import calibrate_structure_thresholds  # noqa: E402


def main() -> int:
    p = argparse.ArgumentParser(description="CALT structure_verify calibration")
    p.add_argument("--min-samples", type=int, default=5)
    p.add_argument(
        "--min-real-samples",
        type=int,
        default=None,
        help="Confirmed samples with paths_json required; synthetic fixtures do not count",
    )
    p.add_argument("--no-synthetic", action="store_true")
    p.add_argument("--include-holdout", action="store_true", help="Calibrate on eval rows too")
    args = p.parse_args()

    result = calibrate_structure_thresholds(
        min_samples=args.min_samples,
        min_real_samples=args.min_real_samples,
        include_synthetic=not args.no_synthetic,
        exclude_holdout=not args.include_holdout,
    )
    print(json.dumps(result.to_dict(), indent=2))
    return 0 if result.status == "calibrated" else 1


if __name__ == "__main__":
    raise SystemExit(main())
