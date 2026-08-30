"""Calibrate structure_verify heuristics from handwriting dataset + fixtures."""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from backend.math.retrain_service import ground_truth_latex
from backend.math.stroke_symbol import paths_json_to_strokes, read_paths_json_for_row
from backend.math.structure_verify import (
    THRESHOLDS_PATH,
    StructureThresholds,
    detect_geometry_signals,
    detect_latex_signals,
    load_thresholds,
    paths_to_stroke_metrics,
    save_thresholds,
    verify_structure,
)
from backend.math.training_log import _read_rows
from backend.paths import ROOT

logger = logging.getLogger(__name__)

CALIBRATION_REPORT_PATH = ROOT / "data" / "math" / "structure_calibration_report.json"


@dataclass
class CalibrationSample:
    latex: str
    metrics: dict[str, Any]
    source: str = "dataset"


@dataclass
class CalibrationResult:
    status: str
    message: str
    sample_count: int
    synthetic_count: int
    real_count: int
    score_before: float
    score_after: float
    thresholds: dict[str, Any] = field(default_factory=dict)
    silence_threshold: float = 0.45
    skip_reasons: dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _bootstrap_synthetic_samples() -> list[CalibrationSample]:
    """Hand-crafted bbox layouts mirroring unit tests — always available."""
    def m(boxes: list[tuple[float, float, float, float]]) -> dict:
        return paths_to_stroke_metrics(
            [
                [(x, y), (x + w, y + h)]
                for x, y, w, h in boxes
            ]
        )

    return [
        CalibrationSample(r"\frac{1}{2}", m([(40, 10, 20, 18), (20, 32, 80, 3), (40, 40, 20, 18)]), "synthetic"),
        CalibrationSample("x + 1", m([(40, 10, 20, 18), (20, 32, 80, 3), (40, 40, 20, 18)]), "synthetic"),
        CalibrationSample(r"x^2", m([(10, 30, 18, 24), (32, 10, 10, 12)]), "synthetic"),
        CalibrationSample("7", m([(30, 25, 20, 30)]), "synthetic"),
        CalibrationSample("12", m([(10, 25, 15, 28), (30, 25, 15, 28)]), "synthetic"),
        CalibrationSample(r"\sqrt{x}", m([(8, 8, 8, 44), (20, 28, 40, 20)]), "synthetic"),
        CalibrationSample("x_1", m([(10, 28, 20, 24), (35, 42, 12, 14)]), "synthetic"),
    ]


def collect_calibration_samples(
    rows: list[dict] | None = None,
    *,
    user_id: int | None = None,
    include_synthetic: bool = True,
) -> tuple[list[CalibrationSample], dict[str, int]]:
    skip: dict[str, int] = {}
    out: list[CalibrationSample] = []

    if include_synthetic:
        out.extend(_bootstrap_synthetic_samples())

    if rows is None:
        rows = _read_rows(user_id)

    for row in rows:
        latex = ground_truth_latex(row)
        if not latex:
            skip["missing_label"] = skip.get("missing_label", 0) + 1
            continue
        raw = read_paths_json_for_row(row)
        if not raw:
            skip["missing_paths_json"] = skip.get("missing_paths_json", 0) + 1
            continue
        strokes = paths_json_to_strokes(raw)
        if not strokes:
            skip["empty_strokes"] = skip.get("empty_strokes", 0) + 1
            continue
        out.append(
            CalibrationSample(
                latex=latex,
                metrics=paths_to_stroke_metrics(strokes),
                source="dataset",
            )
        )

    return out, skip


def _sample_weight(sample: CalibrationSample) -> float:
    """Weight synthetic fixtures higher when real ink is sparse."""
    return 1.0 if sample.source == "dataset" else 1.5


def _hard_fixture_checks(thresholds: StructureThresholds) -> bool:
    """Reject candidates that break canonical geometry layouts from unit tests."""
    frac_boxes = [
        {"x": 40, "y": 10, "w": 20, "h": 18},
        {"x": 20, "y": 32, "w": 80, "h": 3},
        {"x": 40, "y": 40, "w": 20, "h": 18},
    ]
    sup_boxes = [
        {"x": 10, "y": 30, "w": 18, "h": 24},
        {"x": 32, "y": 10, "w": 10, "h": 12},
    ]
    if not detect_geometry_signals(frac_boxes, thresholds=thresholds).has_fraction:
        return False
    if not detect_geometry_signals(sup_boxes, thresholds=thresholds).has_superscript:
        return False
    return True


def _evaluate_thresholds(thresholds: StructureThresholds, samples: list[CalibrationSample]) -> float:
    """Higher is better — rewards agreement + appropriate silence on mismatch."""
    score = 0.0
    for sample in samples:
        w = _sample_weight(sample)
        result = verify_structure(sample.latex, sample.metrics, thresholds=thresholds)
        latex_sig = detect_latex_signals(sample.latex)
        has_structure = any(
            (
                latex_sig.has_fraction,
                latex_sig.has_superscript,
                latex_sig.has_subscript,
                latex_sig.has_sqrt,
            )
        )
        geo = result.geometry
        geo_structure = any(
            (geo.has_fraction, geo.has_superscript, geo.has_subscript, geo.has_sqrt)
        )

        if result.agree:
            if has_structure or not geo_structure:
                score += w * (0.5 + 0.5 * result.structural_confidence)
            else:
                score += w * result.structural_confidence
        else:
            # Mismatch should land below silence threshold (tutor stays quiet).
            if result.structural_confidence < thresholds.silence_threshold:
                score += w * 1.0
            else:
                score -= w * 1.25

        # Simple expressions without structure should not be over-penalized.
        if not has_structure and not geo_structure and result.structural_confidence >= 0.75:
            score += w * 0.35

    return score


def _grid_candidates(base: StructureThresholds) -> list[StructureThresholds]:
    candidates: list[StructureThresholds] = [base]
    for sup_h in (0.55, 0.65, 0.75, 0.85):
        for sup_off in (0.15, 0.22, 0.30, 0.38):
            for geo_pen in (0.08, 0.12, 0.18, 0.24):
                for frac_h in (0.35, 0.45, 0.55):
                    t = StructureThresholds(**asdict(base))
                    t.sup_height_ratio = sup_h
                    t.sup_baseline_offset = sup_off
                    t.geo_only_penalty = geo_pen
                    t.frac_bar_height_ratio = frac_h
                    candidates.append(t)
    return candidates


def _pick_silence_threshold(thresholds: StructureThresholds, samples: list[CalibrationSample]) -> float:
    """Set silence threshold between median agree vs mismatch confidence."""
    agree_conf: list[float] = []
    mismatch_conf: list[float] = []
    for sample in samples:
        r = verify_structure(sample.latex, sample.metrics, thresholds=thresholds)
        if r.agree:
            agree_conf.append(r.structural_confidence)
        else:
            mismatch_conf.append(r.structural_confidence)

    if agree_conf and mismatch_conf:
        low_agree = sorted(agree_conf)[max(0, len(agree_conf) // 10)]
        high_mismatch = sorted(mismatch_conf)[min(len(mismatch_conf) - 1, len(mismatch_conf) * 9 // 10)]
        mid = (low_agree + high_mismatch) / 2.0
        return round(max(0.35, min(0.55, mid)), 3)

    if agree_conf:
        return round(max(0.35, min(0.55, sorted(agree_conf)[len(agree_conf) // 4])), 3)

    return thresholds.silence_threshold


def calibrate_structure_thresholds(
    *,
    min_samples: int = 5,
    user_id: int | None = None,
    include_synthetic: bool = True,
    rows: list[dict] | None = None,
) -> CalibrationResult:
    samples, skip = collect_calibration_samples(
        rows=rows,
        user_id=user_id,
        include_synthetic=include_synthetic,
    )
    real_count = sum(1 for s in samples if s.source == "dataset")
    synthetic_count = len(samples) - real_count

    if len(samples) < min_samples:
        return CalibrationResult(
            status="insufficient_samples",
            message=f"Need at least {min_samples} calibration samples; have {len(samples)}.",
            sample_count=len(samples),
            synthetic_count=synthetic_count,
            real_count=real_count,
            score_before=0.0,
            score_after=0.0,
            skip_reasons=skip,
        )

    current = load_thresholds()
    score_before = _evaluate_thresholds(current, samples)

    best = current
    best_score = score_before
    for candidate in _grid_candidates(current):
        if not _hard_fixture_checks(candidate):
            continue
        s = _evaluate_thresholds(candidate, samples)
        if s > best_score:
            best_score = s
            best = candidate

    best.silence_threshold = _pick_silence_threshold(best, samples)
    score_after = _evaluate_thresholds(best, samples)

    save_thresholds(best)
    mlp_trained = False
    try:
        from backend.math.structure_learned import train_from_labels
        from backend.math.structure_verify import _pen_boxes_in_band

        mlp_samples: list[tuple[list[dict[str, float]], float]] = []
        for sample in samples:
            boxes = _pen_boxes_in_band(sample.metrics, y0=-1e9, y1=1e9)
            if not boxes:
                continue
            result = verify_structure(sample.latex, sample.metrics, thresholds=best)
            mlp_samples.append((boxes, result.structural_confidence))
        if len(mlp_samples) >= 3:
            train_from_labels(mlp_samples)
            mlp_trained = True
    except Exception as e:
        logger.warning("structure MLP train skipped: %s", e)

    report = {
        "sample_count": len(samples),
        "real_count": real_count,
        "synthetic_count": synthetic_count,
        "score_before": round(score_before, 4),
        "score_after": round(score_after, 4),
        "skip_reasons": skip,
        "thresholds": asdict(best),
        "mlp_trained": mlp_trained,
    }
    THRESHOLDS_PATH.parent.mkdir(parents=True, exist_ok=True)
    CALIBRATION_REPORT_PATH.write_text(json.dumps(report, indent=2), encoding="utf-8")

    return CalibrationResult(
        status="calibrated",
        message=(
            f"Calibrated on {len(samples)} samples ({real_count} real). "
            f"Score {score_before:.2f} → {score_after:.2f}."
        ),
        sample_count=len(samples),
        synthetic_count=synthetic_count,
        real_count=real_count,
        score_before=round(score_before, 4),
        score_after=round(score_after, 4),
        thresholds=asdict(best),
        silence_threshold=best.silence_threshold,
        skip_reasons=skip,
    )
