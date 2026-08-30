"""Unit tests for stuckness + Socratic guard (no OCR model download)."""

from backend.math.intervention_handler import (
    STUCKNESS_THRESHOLD,
    _hint_passes_socratic_check,
    compute_stuckness,
)
from backend.math.ocr_service import OcrResult


def test_compute_stuckness_idle_and_gamma():
    score = compute_stuckness(
        gamma=85,
        canvas_idle_seconds=90,
        eraser_events=0,
    )
    assert score >= STUCKNESS_THRESHOLD


def test_compute_stuckness_low_signal():
    score = compute_stuckness(gamma=20, canvas_idle_seconds=5, eraser_events=0)
    assert score < STUCKNESS_THRESHOLD


def test_compute_stuckness_incomplete_ocr_nudge():
    ocr = OcrResult(latex=r"\frac{a}{", incomplete_step=True, confidence=0.4, preprocess_applied=True)
    score = compute_stuckness(canvas_idle_seconds=80, eraser_events=2, ocr=ocr)
    assert score >= 0.35


def test_socratic_guard_rejects_answer():
    assert not _hint_passes_socratic_check("So x = 5", "Does that work?")


def test_socratic_guard_allows_hint():
    assert _hint_passes_socratic_check("Try isolating the variable first.", "What operation comes next?")
