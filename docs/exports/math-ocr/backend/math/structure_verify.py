"""
Geometric structural verifier (relation layer v0).

Pure geometry on stroke bboxes within a line band — detects superscript /
subscript candidates, fraction bars, and sqrt-like enclosures — then
cross-checks against TexTeller LaTeX to produce structural_confidence.

Thresholds load from ``data/math/structure_thresholds.json`` when present
(recalibrate via ``POST /api/math/train/recalibrate-structure``).
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

from backend.paths import ROOT

THRESHOLDS_PATH = ROOT / "data" / "math" / "structure_thresholds.json"


@dataclass
class StructureThresholds:
    sup_height_ratio: float = 0.7
    sup_baseline_offset: float = 0.25
    sub_height_ratio: float = 0.7
    sub_top_offset: float = 0.55
    sub_baseline_margin: float = 0.1
    frac_aspect_min: float = 3.0
    frac_bar_height_ratio: float = 0.45
    sqrt_height_ratio: float = 1.4
    sqrt_width_ratio: float = 1.2
    geo_only_penalty: float = 0.15
    no_structure_confidence: float = 0.9
    no_metrics_confidence: float = 0.55
    empty_latex_confidence: float = 0.4
    silence_threshold: float = 0.45


# Default until load_thresholds() runs; kept for imports/tests.
STRUCTURAL_SILENCE_THRESHOLD = StructureThresholds().silence_threshold


@dataclass
class StructureSignals:
    has_superscript: bool = False
    has_subscript: bool = False
    has_fraction: bool = False
    has_sqrt: bool = False
    has_matrix: bool = False
    notes: list[str] = field(default_factory=list)


@dataclass
class StructureVerifyResult:
    structural_confidence: float
    geometry: StructureSignals
    latex_signals: StructureSignals
    agree: bool
    reason: str = ""


def paths_to_stroke_metrics(strokes: list[list[tuple[float, float]]]) -> dict[str, Any]:
    """Build stroke_metrics dict from normalized stroke point lists."""
    metrics_strokes: list[dict[str, Any]] = []
    for i, stroke in enumerate(strokes):
        if not stroke:
            continue
        xs = [p[0] for p in stroke]
        ys = [p[1] for p in stroke]
        x0, y0 = min(xs), min(ys)
        x1, y1 = max(xs), max(ys)
        metrics_strokes.append(
            {
                "strokeIndex": i,
                "tool": "pen",
                "bbox": {
                    "x": float(x0),
                    "y": float(y0),
                    "w": float(max(x1 - x0, 1.0)),
                    "h": float(max(y1 - y0, 1.0)),
                },
            }
        )
    return {"strokes": metrics_strokes, "totalStrokes": len(metrics_strokes)}


def _sync_silence_constant(thresholds: StructureThresholds) -> None:
    global STRUCTURAL_SILENCE_THRESHOLD
    STRUCTURAL_SILENCE_THRESHOLD = thresholds.silence_threshold


@lru_cache(maxsize=1)
def load_thresholds() -> StructureThresholds:
    if not THRESHOLDS_PATH.is_file():
        t = StructureThresholds()
        _sync_silence_constant(t)
        return t
    try:
        data = json.loads(THRESHOLDS_PATH.read_text(encoding="utf-8"))
        t = StructureThresholds(**{k: v for k, v in data.items() if k in StructureThresholds.__dataclass_fields__})
        _sync_silence_constant(t)
        return t
    except Exception:
        t = StructureThresholds()
        _sync_silence_constant(t)
        return t


def save_thresholds(thresholds: StructureThresholds) -> Path:
    THRESHOLDS_PATH.parent.mkdir(parents=True, exist_ok=True)
    THRESHOLDS_PATH.write_text(json.dumps(asdict(thresholds), indent=2), encoding="utf-8")
    load_thresholds.cache_clear()
    _sync_silence_constant(thresholds)
    return THRESHOLDS_PATH


def get_silence_threshold() -> float:
    return load_thresholds().silence_threshold


def _pen_boxes_in_band(
    stroke_metrics: dict[str, Any] | None,
    *,
    y0: float,
    y1: float,
    x0: float = 0.0,
    x1: float | None = None,
) -> list[dict[str, float]]:
    if not stroke_metrics or not isinstance(stroke_metrics, dict):
        return []
    out: list[dict[str, float]] = []
    for s in stroke_metrics.get("strokes") or []:
        if not isinstance(s, dict) or s.get("tool") != "pen":
            continue
        bbox = s.get("bbox") or {}
        try:
            x = float(bbox["x"])
            y = float(bbox["y"])
            w = float(bbox["w"])
            h = float(bbox["h"])
        except (KeyError, TypeError, ValueError):
            continue
        cy = y + h / 2.0
        if cy < y0 or cy > y1:
            continue
        if x1 is not None and (x + w < x0 or x > x1):
            continue
        out.append({"x": x, "y": y, "w": max(w, 1.0), "h": max(h, 1.0)})
    return out


def detect_geometry_signals(
    boxes: list[dict[str, float]],
    *,
    thresholds: StructureThresholds | None = None,
) -> StructureSignals:
    """Heuristic spatial-relation detectors from stroke bboxes alone."""
    t = thresholds or load_thresholds()
    sig = StructureSignals()
    if len(boxes) < 2:
        return sig

    heights = [b["h"] for b in boxes]
    widths = [b["w"] for b in boxes]
    median_h = sorted(heights)[len(heights) // 2]
    median_w = sorted(widths)[len(widths) // 2]
    bottoms = sorted(b["y"] + b["h"] for b in boxes)
    baseline = bottoms[len(bottoms) // 2]
    tops = sorted(b["y"] for b in boxes)
    top_line = tops[len(tops) // 2]

    for b in boxes:
        aspect = b["w"] / max(b["h"], 1.0)
        if aspect >= t.frac_aspect_min and b["h"] <= max(4.0, t.frac_bar_height_ratio * median_h):
            mid_y = b["y"] + b["h"] / 2.0
            above = any(ob["y"] + ob["h"] < mid_y - 1 for ob in boxes if ob is not b)
            below = any(ob["y"] > mid_y + 1 for ob in boxes if ob is not b)
            if above and below:
                sig.has_fraction = True
                sig.notes.append("fraction_bar")

        if b["h"] < t.sup_height_ratio * median_h and (b["y"] + b["h"]) < baseline - t.sup_baseline_offset * median_h:
            sig.has_superscript = True
            sig.notes.append("superscript_candidate")

        if b["h"] < t.sub_height_ratio * median_h and b["y"] > top_line + t.sub_top_offset * median_h:
            if (b["y"] + b["h"]) > baseline - t.sub_baseline_margin * median_h:
                sig.has_subscript = True
                sig.notes.append("subscript_candidate")

        if b["h"] >= t.sqrt_height_ratio * median_h and b["w"] <= t.sqrt_width_ratio * median_w:
            right_ink = any(ob["x"] > b["x"] + b["w"] for ob in boxes if ob is not b)
            if right_ink:
                sig.has_sqrt = True
                sig.notes.append("sqrt_candidate")

    try:
        from backend.math.structure_learned import detect_matrix_layout

        if detect_matrix_layout(boxes):
            sig.has_matrix = True
            sig.notes.append("matrix_grid")
    except Exception:
        pass

    return sig


_FRAC_RE = re.compile(r"\\frac\b|\\dfrac\b|\\tfrac\b")
_SQRT_RE = re.compile(r"\\sqrt\b")
_SUP_RE = re.compile(r"\^|\\sp\b")
_SUB_RE = re.compile(r"(?<!\\)_|\\sb\b")
_MATRIX_RE = re.compile(r"\\begin\{(matrix|pmatrix|bmatrix|array|aligned)\}")


def detect_latex_signals(latex: str) -> StructureSignals:
    text = latex or ""
    return StructureSignals(
        has_superscript=bool(_SUP_RE.search(text)),
        has_subscript=bool(_SUB_RE.search(text)),
        has_fraction=bool(_FRAC_RE.search(text)),
        has_sqrt=bool(_SQRT_RE.search(text)),
        has_matrix=bool(_MATRIX_RE.search(text)),
    )


def verify_structure(
    latex: str,
    stroke_metrics: dict[str, Any] | None = None,
    *,
    band_bbox: dict[str, float] | None = None,
    thresholds: StructureThresholds | None = None,
) -> StructureVerifyResult:
    """
    Cross-check geometric structure hints against LaTeX tokens.

    Returns structural_confidence in [0, 1]. Low confidence should silence
    the tutor (Phase 2 silence rule).
    """
    t = thresholds or load_thresholds()

    if band_bbox:
        boxes = _pen_boxes_in_band(
            stroke_metrics,
            y0=float(band_bbox.get("y", 0)),
            y1=float(band_bbox.get("y", 0)) + float(band_bbox.get("h", 0)),
            x0=float(band_bbox.get("x", 0)),
            x1=float(band_bbox.get("x", 0)) + float(band_bbox.get("w", 0))
            if band_bbox.get("w")
            else None,
        )
    else:
        boxes = _pen_boxes_in_band(stroke_metrics, y0=-1e9, y1=1e9)

    geometry = detect_geometry_signals(boxes, thresholds=t)
    latex_sig = detect_latex_signals(latex)

    if not boxes:
        base = t.no_metrics_confidence if (latex or "").strip() else t.empty_latex_confidence
        return StructureVerifyResult(
            structural_confidence=base,
            geometry=geometry,
            latex_signals=latex_sig,
            agree=True,
            reason="no_stroke_metrics",
        )

    checks = [
        ("fraction", geometry.has_fraction, latex_sig.has_fraction),
        ("superscript", geometry.has_superscript, latex_sig.has_superscript),
        ("subscript", geometry.has_subscript, latex_sig.has_subscript),
        ("sqrt", geometry.has_sqrt, latex_sig.has_sqrt),
        ("matrix", geometry.has_matrix, latex_sig.has_matrix),
    ]

    active = [(name, g, l) for name, g, l in checks if g or l]
    if not active:
        return StructureVerifyResult(
            structural_confidence=t.no_structure_confidence if (latex or "").strip() else t.empty_latex_confidence,
            geometry=geometry,
            latex_signals=latex_sig,
            agree=True,
            reason="no_structure_claimed",
        )

    agreements = sum(1 for _n, g, l in active if g == l)
    ratio = agreements / len(active)
    mismatches = [n for n, g, l in active if g != l]

    geo_only = sum(1 for _n, g, l in active if g and not l)
    penalty = t.geo_only_penalty * geo_only
    confidence = max(0.0, min(1.0, ratio - penalty))

    try:
        from backend.math.structure_learned import predict_learned_confidence

        learned = predict_learned_confidence(boxes)
        confidence = max(0.0, min(1.0, confidence + learned.confidence_boost))
    except Exception:
        pass

    if mismatches:
        try:
            from backend.math.structure_misseg_log import log_mismatch

            log_mismatch(
                latex=latex,
                reason=",".join(mismatches),
                geometry_notes=geometry.notes,
                band_bbox=band_bbox,
            )
        except Exception:
            pass

    return StructureVerifyResult(
        structural_confidence=round(confidence, 3),
        geometry=geometry,
        latex_signals=latex_sig,
        agree=len(mismatches) == 0,
        reason=("ok" if not mismatches else "mismatch:" + ",".join(mismatches)),
    )


# Warm defaults on import.
load_thresholds()
