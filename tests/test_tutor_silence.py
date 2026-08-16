"""Tutor silence rule — low structural / OCR confidence stays quiet."""

from backend.math.intervention_handler import (
    OCR_CONFIDENCE_SILENCE_THRESHOLD,
    InterventionResult,
    build_intervention,
)
from backend.math.structure_verify import STRUCTURAL_SILENCE_THRESHOLD


def test_silence_thresholds_are_sane():
    assert 0.3 <= OCR_CONFIDENCE_SILENCE_THRESHOLD <= 0.6
    assert 0.3 <= STRUCTURAL_SILENCE_THRESHOLD <= 0.6


def test_intervention_result_carries_silence_fields():
    r = InterventionResult(
        session_snapshot_id="s1",
        latex="",
        incomplete_step=True,
        confidence=0.2,
        stuckness=0.1,
        triggered=False,
        hint="",
        question="",
        detected_concept="x",
        use_llm=False,
        structural_confidence=0.2,
        tutor_silent=True,
    )
    assert r.tutor_silent is True
    assert r.structural_confidence == 0.2


def test_build_intervention_empty_canvas_image_no_crash():
    # No canvas → no OCR → not silent (nothing to silence about).
    result = build_intervention(
        canvas_image="",
        snapshot_id="snap-test",
        canvas_idle_seconds=10,
    )
    assert result.session_snapshot_id == "snap-test"
    assert result.tutor_silent is False
