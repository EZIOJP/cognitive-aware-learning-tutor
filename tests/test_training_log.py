"""Training log helpers — no model download."""

from backend.math.training_log import _latex_agree, training_progress


def test_latex_agree_match():
    assert _latex_agree("7", "7", "") == "true"


def test_latex_agree_corrected():
    assert _latex_agree("l", "1", "") == "corrected"


def test_training_progress_empty():
    prog = training_progress(user_id=999_999)
    assert prog["total_samples"] == 0
    assert prog["accuracy"] == 0.0
