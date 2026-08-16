"""
Geometric structural verifier (relation layer v0).

Pure geometry on stroke bboxes within a line band — detects superscript /
subscript candidates, fraction bars, and sqrt-like enclosures — then
cross-checks against TexTeller LaTeX to produce structural_confidence.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any


@dataclass
class StructureSignals:
    has_superscript: bool = False
    has_subscript: bool = False
    has_fraction: bool = False
    has_sqrt: bool = False
    notes: list[str] = field(default_factory=list)


@dataclass
class StructureVerifyResult:
    structural_confidence: float
    geometry: StructureSignals
    latex_signals: StructureSignals
    agree: bool
    reason: str = ""


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


def detect_geometry_signals(boxes: list[dict[str, float]]) -> StructureSignals:
    """Heuristic spatial-relation detectors from stroke bboxes alone."""
    sig = StructureSignals()
    if len(boxes) < 2:
        return sig

    heights = [b["h"] for b in boxes]
    widths = [b["w"] for b in boxes]
    median_h = sorted(heights)[len(heights) // 2]
    median_w = sorted(widths)[len(widths) // 2]
    # Baseline ≈ median of box bottoms weighted toward larger glyphs.
    bottoms = sorted(b["y"] + b["h"] for b in boxes)
    baseline = bottoms[len(bottoms) // 2]
    tops = sorted(b["y"] for b in boxes)
    top_line = tops[len(tops) // 2]

    for b in boxes:
        aspect = b["w"] / max(b["h"], 1.0)
        # Fraction bar: wide, flat stroke with ink above and below.
        if aspect >= 3.0 and b["h"] <= max(4.0, 0.45 * median_h):
            mid_y = b["y"] + b["h"] / 2.0
            above = any(ob["y"] + ob["h"] < mid_y - 1 for ob in boxes if ob is not b)
            below = any(ob["y"] > mid_y + 1 for ob in boxes if ob is not b)
            if above and below:
                sig.has_fraction = True
                sig.notes.append("fraction_bar")

        # Superscript: smaller glyph sitting clearly above baseline.
        if b["h"] < 0.7 * median_h and (b["y"] + b["h"]) < baseline - 0.25 * median_h:
            sig.has_superscript = True
            sig.notes.append("superscript_candidate")

        # Subscript: smaller glyph sitting clearly below top-of-line cluster.
        if b["h"] < 0.7 * median_h and b["y"] > top_line + 0.55 * median_h:
            if (b["y"] + b["h"]) > baseline - 0.1 * median_h:
                sig.has_subscript = True
                sig.notes.append("subscript_candidate")

        # Sqrt-like enclosure: tall stroke spanning most of the band height,
        # with ink to its right (radicand).
        if b["h"] >= 1.4 * median_h and b["w"] <= 1.2 * median_w:
            right_ink = any(ob["x"] > b["x"] + b["w"] for ob in boxes if ob is not b)
            if right_ink:
                sig.has_sqrt = True
                sig.notes.append("sqrt_candidate")

    return sig


_FRAC_RE = re.compile(r"\\frac\b|\\dfrac\b|\\tfrac\b")
_SQRT_RE = re.compile(r"\\sqrt\b")
_SUP_RE = re.compile(r"\^|\\sp\b")
_SUB_RE = re.compile(r"(?<!\\)_|\\sb\b")


def detect_latex_signals(latex: str) -> StructureSignals:
    t = latex or ""
    return StructureSignals(
        has_superscript=bool(_SUP_RE.search(t)),
        has_subscript=bool(_SUB_RE.search(t)),
        has_fraction=bool(_FRAC_RE.search(t)),
        has_sqrt=bool(_SQRT_RE.search(t)),
    )


def verify_structure(
    latex: str,
    stroke_metrics: dict[str, Any] | None = None,
    *,
    band_bbox: dict[str, float] | None = None,
) -> StructureVerifyResult:
    """
    Cross-check geometric structure hints against LaTeX tokens.

    Returns structural_confidence in [0, 1]. Low confidence should silence
    the tutor (Phase 2 silence rule).
    """
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

    geometry = detect_geometry_signals(boxes)
    latex_sig = detect_latex_signals(latex)

    # If no strokes available, confidence tracks latex completeness only lightly.
    if not boxes:
        base = 0.55 if (latex or "").strip() else 0.2
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
    ]

    # Only score relations that geometry OR latex claims — ignore mutual absences.
    active = [(name, g, l) for name, g, l in checks if g or l]
    if not active:
        # Simple line (no structure claimed) — high structural confidence.
        return StructureVerifyResult(
            structural_confidence=0.9 if (latex or "").strip() else 0.4,
            geometry=geometry,
            latex_signals=latex_sig,
            agree=True,
            reason="no_structure_claimed",
        )

    agreements = sum(1 for _n, g, l in active if g == l)
    ratio = agreements / len(active)
    mismatches = [n for n, g, l in active if g != l]

    # Geometry-only claim without latex support is more damning than the reverse
    # (OCR may miss a superscript that geometry sees).
    geo_only = sum(1 for _n, g, l in active if g and not l)
    penalty = 0.15 * geo_only
    confidence = max(0.0, min(1.0, ratio - penalty))

    return StructureVerifyResult(
        structural_confidence=round(confidence, 3),
        geometry=geometry,
        latex_signals=latex_sig,
        agree=len(mismatches) == 0,
        reason=("ok" if not mismatches else "mismatch:" + ",".join(mismatches)),
    )


# Tutor silence threshold — below this, intervention stays quiet.
STRUCTURAL_SILENCE_THRESHOLD = 0.45
