#!/usr/bin/env python3
"""Export DSC_handwriting_dataset.csv for TexTeller fine-tune; optionally launch training."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.math.retrain_service import export_texteller_dataset, run_retrain_job  # noqa: E402


def main() -> int:
    p = argparse.ArgumentParser(description="CALT TexTeller retrain export / train")
    p.add_argument(
        "--mode",
        choices=("export", "train"),
        default="export",
        help="export: write dataset only; train: export then accelerate launch (needs TEXTELLER_TRAIN_REPO)",
    )
    p.add_argument("--min-samples", type=int, default=None, help="Override retrain_threshold from curriculum")
    p.add_argument("--user-id", type=int, default=None, help="Limit export to one user")
    args = p.parse_args()

    result = run_retrain_job(mode=args.mode, min_samples=args.min_samples, user_id=args.user_id)
    print(json.dumps(result, indent=2))
    status = result.get("status", "")
    if status in ("exported", "training_completed"):
        return 0
    if status == "export_only_train_failed" and result.get("exported", 0) > 0:
        return 2
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
