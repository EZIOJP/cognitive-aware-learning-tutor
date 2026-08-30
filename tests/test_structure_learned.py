"""Structure learned verifier + matrix detection."""

from __future__ import annotations

from backend.math.structure_learned import detect_matrix_layout, predict_learned_confidence
from backend.math.structure_verify import detect_geometry_signals, detect_latex_signals


def test_matrix_layout_detected():
    boxes = [
        {"x": 0, "y": 0, "w": 20, "h": 30},
        {"x": 30, "y": 0, "w": 20, "h": 30},
        {"x": 60, "y": 0, "w": 20, "h": 30},
        {"x": 0, "y": 40, "w": 20, "h": 30},
        {"x": 30, "y": 40, "w": 20, "h": 30},
        {"x": 60, "y": 40, "w": 20, "h": 30},
    ]
    assert detect_matrix_layout(boxes) is True
    geo = detect_geometry_signals(boxes)
    assert geo.has_matrix is True


def test_latex_matrix_signal():
    sig = detect_latex_signals(r"\begin{pmatrix}1&2\\3&4\end{pmatrix}")
    assert sig.has_matrix is True


def test_learned_confidence_runs():
    boxes = [{"x": 0, "y": 0, "w": 10, "h": 10}]
    result = predict_learned_confidence(boxes)
    assert -0.5 <= result.confidence_boost <= 0.5
