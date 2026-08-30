"""Tests for line_detect + structure_verify (no TexTeller required)."""

from __future__ import annotations

import numpy as np
import pytest
from PIL import Image, ImageDraw

from backend.math.line_detect import (
    LineBand,
    apply_fraction_guard,
    detect_line_bands,
    group_lines_from_strokes,
    split_lines_projection,
)
from backend.math.structure_verify import (
    STRUCTURAL_SILENCE_THRESHOLD,
    detect_geometry_signals,
    detect_latex_signals,
    load_thresholds,
    verify_structure,
)


def _metrics_from_boxes(boxes: list[tuple[float, float, float, float]]) -> dict:
    strokes = []
    for i, (x, y, w, h) in enumerate(boxes):
        strokes.append(
            {
                "strokeIndex": i,
                "tool": "pen",
                "bbox": {"x": x, "y": y, "w": w, "h": h},
                "gridCell": {"col": 0, "row": 0},
            }
        )
    return {"strokes": strokes, "totalStrokes": len(strokes)}


def test_group_lines_from_strokes_three_rows():
    # Three well-separated horizontal ink rows.
    metrics = _metrics_from_boxes(
        [
            (10, 10, 80, 18),
            (100, 12, 40, 16),
            (10, 60, 120, 20),
            (20, 110, 90, 18),
        ]
    )
    bands = group_lines_from_strokes(metrics)
    assert len(bands) == 3
    assert bands[0].y0 < bands[1].y0 < bands[2].y0
    assert bands[0].source == "stroke_bbox"


def test_group_lines_empty_metrics():
    assert group_lines_from_strokes(None) == []
    assert group_lines_from_strokes({}) == []


def test_fraction_guard_merges_close_bands():
    # Numerator / bar / denominator should merge when gaps are tiny.
    bands = [
        LineBand(y0=10, y1=30, x0=10, x1=80, source="stroke_bbox"),
        LineBand(y0=32, y1=36, x0=10, x1=80, source="stroke_bbox"),  # bar
        LineBand(y0=38, y1=58, x0=10, x1=80, source="stroke_bbox"),
        LineBand(y0=100, y1=120, x0=10, x1=80, source="stroke_bbox"),  # next line
    ]
    merged = apply_fraction_guard(bands, merge_ratio=0.5)
    assert len(merged) == 2
    assert merged[0].y0 == 10
    assert merged[0].y1 == 58
    assert merged[1].y0 == 100


def test_split_lines_projection_multi():
    img = Image.new("RGB", (200, 180), "white")
    d = ImageDraw.Draw(img)
    d.line([(20, 30), (180, 30)], fill="black", width=4)
    d.line([(20, 90), (180, 90)], fill="black", width=4)
    d.line([(20, 150), (180, 150)], fill="black", width=4)
    bands = split_lines_projection(img, min_gap_rows=8)
    assert len(bands) == 3
    assert all(b.source == "projection" for b in bands)


def test_detect_line_bands_prefers_strokes():
    img = Image.new("RGB", (200, 160), "white")
    d = ImageDraw.Draw(img)
    d.line([(20, 40), (180, 40)], fill="black", width=4)
    d.line([(20, 120), (180, 120)], fill="black", width=4)
    metrics = _metrics_from_boxes([(20, 30, 160, 20), (20, 110, 160, 20)])
    bands = detect_line_bands(img, metrics, pad=4)
    assert len(bands) == 2
    assert bands[0].source == "stroke_bbox"


def test_geometry_detects_fraction_bar():
    boxes = [
        {"x": 40, "y": 10, "w": 20, "h": 18},  # numerator
        {"x": 20, "y": 32, "w": 80, "h": 3},  # bar
        {"x": 40, "y": 40, "w": 20, "h": 18},  # denominator
    ]
    sig = detect_geometry_signals(boxes)
    assert sig.has_fraction


def test_geometry_detects_superscript():
    load_thresholds.cache_clear()
    boxes = [
        {"x": 10, "y": 30, "w": 18, "h": 24},  # base
        {"x": 32, "y": 10, "w": 10, "h": 12},  # superscript
    ]
    sig = detect_geometry_signals(boxes)
    assert sig.has_superscript


def test_latex_signals():
    sig = detect_latex_signals(r"x^2 + \frac{a}{b} + \sqrt{c}")
    assert sig.has_superscript
    assert sig.has_fraction
    assert sig.has_sqrt


def test_verify_structure_agreement_high():
    metrics = _metrics_from_boxes(
        [
            (40, 10, 20, 18),
            (20, 32, 80, 3),
            (40, 40, 20, 18),
        ]
    )
    result = verify_structure(r"\frac{1}{2}", metrics)
    assert result.agree
    assert result.structural_confidence >= 0.7


def test_verify_structure_mismatch_lowers_confidence():
    # Geometry sees a fraction bar; latex has none.
    metrics = _metrics_from_boxes(
        [
            (40, 10, 20, 18),
            (20, 32, 80, 3),
            (40, 40, 20, 18),
        ]
    )
    result = verify_structure("x + 1", metrics)
    assert not result.agree
    assert result.structural_confidence < STRUCTURAL_SILENCE_THRESHOLD or result.structural_confidence < 0.7
    assert "fraction" in result.reason


def test_verify_structure_no_metrics_neutral():
    result = verify_structure("x+1", None)
    assert result.reason == "no_stroke_metrics"
    assert 0.4 <= result.structural_confidence <= 0.7


def test_tutor_silence_threshold_constant():
    assert 0.3 <= STRUCTURAL_SILENCE_THRESHOLD <= 0.6
