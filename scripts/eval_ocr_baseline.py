"""
Score the current OCR stack against the frozen held-out split and save a baseline.

Run this before any retrain so later runs have a number to beat. Comparing two
baselines is the only honest way to tell whether a fine-tune helped, since the
calibration and export paths both measure themselves on data they fit.

  python scripts/eval_ocr_baseline.py                     # eval holdout, save baseline
  python scripts/eval_ocr_baseline.py --label pre-finetune
  python scripts/eval_ocr_baseline.py --compare           # diff against previous
  python scripts/eval_ocr_baseline.py --split train       # sanity check (will look better)
  python scripts/eval_ocr_baseline.py --distribution-only # class balance, no OCR
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.eval_ocr_cdm import _normalize, cdm_score  # noqa: E402

BASELINE_DIR = ROOT / "data" / "math" / "ocr_baselines"


def _load_rows(split: str, tier: str | None) -> list[dict]:
    from backend.math.holdout import split_rows
    from backend.math.training_log import _read_rows

    rows = _read_rows()
    train, held = split_rows(rows)
    selected = {"holdout": held, "train": train, "all": rows}[split]
    if tier:
        selected = [r for r in selected if (r.get("tier") or "").strip() == tier]
    return selected


def _distribution(rows: list[dict]) -> dict[str, Any]:
    """Per-tier and per-label counts — a raw total can hide a badly skewed set."""
    from backend.math.retrain_service import ground_truth_latex

    tiers = Counter((r.get("tier") or "unknown").strip() or "unknown" for r in rows)
    labels = Counter(_normalize(ground_truth_latex(r)) for r in rows if ground_truth_latex(r))
    singletons = sum(1 for c in labels.values() if c == 1)
    top = labels.most_common(15)
    return {
        "rows": len(rows),
        "by_tier": dict(tiers.most_common()),
        "distinct_labels": len(labels),
        "labels_seen_once": singletons,
        "most_common_labels": [{"label": k, "count": v} for k, v in top],
        "top_label_share": round(top[0][1] / max(len(rows), 1), 4) if top else 0.0,
    }


def _evaluate(rows: list[dict], limit: int | None) -> dict[str, Any]:
    from PIL import Image

    from backend.math.answer_grade import answers_equivalent
    from backend.math.ocr_engine import recognize_crop
    from backend.math.retrain_service import ground_truth_latex, resolve_png_path

    usable = [r for r in rows if ground_truth_latex(r) and resolve_png_path(r) is not None]
    if limit:
        usable = usable[:limit]

    details: list[dict[str, Any]] = []
    exact = 0
    equivalent = 0
    cdm_total = 0.0
    failed = 0

    for i, row in enumerate(usable, 1):
        ref = ground_truth_latex(row)
        png = resolve_png_path(row)
        try:
            with Image.open(png) as img:
                result = recognize_crop(img.convert("RGB"))
            pred = result.latex
            source = result.source
            confidence = result.confidence
        except Exception as e:
            failed += 1
            pred, source, confidence = "", f"error:{type(e).__name__}", 0.0

        is_exact = bool(pred) and _normalize(pred) == _normalize(ref)
        # String equality punishes \frac vs \dfrac; equivalence is what actually matters.
        is_equiv = is_exact or (bool(pred) and answers_equivalent(ref, pred))
        score = cdm_score(pred, ref)

        exact += int(is_exact)
        equivalent += int(is_equiv)
        cdm_total += score
        details.append(
            {
                "sample_id": (row.get("sample_id") or "").strip(),
                "tier": (row.get("tier") or "").strip(),
                "ref": ref,
                "pred": pred,
                "exact": is_exact,
                "equivalent": is_equiv,
                "cdm": round(score, 4),
                "source": source,
                "confidence": round(float(confidence), 4),
            }
        )
        print(f"  [{i}/{len(usable)}] cdm={score:.3f} {'=' if is_equiv else 'x'} {pred[:48]!r}")

    n = max(len(usable), 1)
    return {
        "evaluated": len(usable),
        "ocr_failures": failed,
        "exact_match": round(exact / n, 4),
        "sympy_equivalent": round(equivalent / n, 4),
        "cdm_avg": round(cdm_total / n, 4),
        "details": details,
    }


def _engine_info() -> dict[str, Any]:
    import os

    from backend.math.onnx_providers import active_execution_provider
    from backend.math.texteller_onnx import active_model_id

    return {
        "execution_provider": active_execution_provider() or "unknown",
        "active_model_id": active_model_id(),
        "finetuned_model": os.getenv("TEXTELLER_FINETUNED_MODEL", "").strip(),
        "primary_engine": os.getenv("OCR_PRIMARY_ENGINE", "auto"),
        "onnx_device": os.getenv("OCR_ONNX_DEVICE", "auto"),
    }


def _previous_baseline(split: str) -> dict[str, Any] | None:
    if not BASELINE_DIR.is_dir():
        return None
    files = sorted((p for p in BASELINE_DIR.glob("*.json")), reverse=True)
    for path in files:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if data.get("split") == split:
            return data
    return None


def _print_delta(previous: dict[str, Any], current: dict[str, Any]) -> None:
    print(f"\nCompared against {previous.get('label') or previous.get('created_at')}:")
    for key in ("exact_match", "sympy_equivalent", "cdm_avg"):
        old = float(previous.get(key, 0.0))
        new = float(current.get(key, 0.0))
        arrow = "+" if new > old else ("-" if new < old else "=")
        print(f"  {key:18} {old:.4f} -> {new:.4f}  ({arrow}{abs(new - old):.4f})")


def main() -> None:
    parser = argparse.ArgumentParser(description="Baseline OCR accuracy on the held-out split")
    parser.add_argument("--split", choices=("holdout", "train", "all"), default="holdout")
    parser.add_argument("--tier", default=None, help="Only rows with this tier")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--label", default="", help="Name this baseline, e.g. pre-finetune")
    parser.add_argument("--compare", action="store_true", help="Diff against previous baseline")
    parser.add_argument("--distribution-only", action="store_true", help="Class balance, no OCR")
    parser.add_argument("--no-save", action="store_true")
    args = parser.parse_args()

    rows = _load_rows(args.split, args.tier)
    distribution = _distribution(rows)

    print(f"split={args.split} rows={distribution['rows']}")
    print(f"  tiers: {distribution['by_tier']}")
    print(
        f"  {distribution['distinct_labels']} distinct labels, "
        f"{distribution['labels_seen_once']} seen once, "
        f"top label is {distribution['top_label_share'] * 100:.1f}% of rows"
    )

    if args.distribution_only:
        for item in distribution["most_common_labels"]:
            print(f"    {item['count']:4d}  {item['label'][:60]}")
        return

    if not rows:
        print("\nNo rows in this split. Collect samples, then freeze a holdout.")
        return

    print("\nRunning OCR...")
    metrics = _evaluate(rows, args.limit)
    details = metrics.pop("details")

    payload = {
        "created_at": datetime.now(UTC).isoformat(),
        "label": args.label,
        "split": args.split,
        "tier": args.tier or "",
        "engine": _engine_info(),
        "distribution": distribution,
        **metrics,
    }

    print(
        f"\nevaluated={metrics['evaluated']}  exact={metrics['exact_match']:.4f}  "
        f"equivalent={metrics['sympy_equivalent']:.4f}  cdm={metrics['cdm_avg']:.4f}"
    )
    print(f"provider={payload['engine']['execution_provider']}")
    if metrics["ocr_failures"]:
        print(f"WARNING: {metrics['ocr_failures']} samples raised during OCR")

    if args.compare:
        previous = _previous_baseline(args.split)
        if previous:
            _print_delta(previous, metrics)
        else:
            print("\nNo previous baseline for this split.")

    if args.no_save:
        return

    BASELINE_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    suffix = f"__{args.label}" if args.label else ""
    out = BASELINE_DIR / f"{stamp}__{args.split}{suffix}.json"
    out.write_text(json.dumps({**payload, "details": details}, indent=2), encoding="utf-8")
    print(f"\nSaved {out.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
