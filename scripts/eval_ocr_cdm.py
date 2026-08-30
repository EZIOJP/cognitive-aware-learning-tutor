"""CDM (Character Detection Metric) eval for local OCR CSV exports (Phase 3)."""

from __future__ import annotations

import argparse
import csv
import re
from dataclasses import dataclass
from pathlib import Path


def _normalize(s: str) -> str:
    text = (s or "").strip()
    text = re.sub(r"\s+", "", text)
    text = text.replace("$", "")
    return text.lower()


def cdm_score(pred: str, ref: str) -> float:
    """Simple character-level F1 proxy (CDM-lite)."""
    p = _normalize(pred)
    r = _normalize(ref)
    if not r and not p:
        return 1.0
    if not r or not p:
        return 0.0
    # multiset overlap
    from collections import Counter

    cp, cr = Counter(p), Counter(r)
    overlap = sum((cp & cr).values())
    prec = overlap / len(p)
    rec = overlap / len(r)
    if prec + rec == 0:
        return 0.0
    return 2 * prec * rec / (prec + rec)


@dataclass
class RowResult:
    pred: str
    ref: str
    score: float


def eval_csv(path: Path, *, pred_col: str = "predicted_latex", ref_col: str = "confirmed_latex") -> list[RowResult]:
    rows: list[RowResult] = []
    with path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            pred = row.get(pred_col, "")
            ref = row.get(ref_col, "")
            rows.append(RowResult(pred=pred, ref=ref, score=cdm_score(pred, ref)))
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description="CDM-lite eval on training CSV")
    parser.add_argument("csv", type=Path, help="CSV with predicted + confirmed LaTeX columns")
    parser.add_argument("--pred-col", default="predicted_latex")
    parser.add_argument("--ref-col", default="confirmed_latex")
    args = parser.parse_args()
    results = eval_csv(args.csv, pred_col=args.pred_col, ref_col=args.ref_col)
    if not results:
        print("No rows")
        return
    avg = sum(r.score for r in results) / len(results)
    print(f"rows={len(results)}  cdm_avg={avg:.4f}")
    for i, r in enumerate(results[:5]):
        print(f"  [{i}] score={r.score:.3f} pred={r.pred[:40]!r} ref={r.ref[:40]!r}")


if __name__ == "__main__":
    main()
