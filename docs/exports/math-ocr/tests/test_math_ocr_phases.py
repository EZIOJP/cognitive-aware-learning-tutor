"""Tests for Gemini 3-phase OCR additions (no model weights required)."""

import json

from backend.math.latex_repair import repair_latex
from backend.math.latex_validate import bracket_balance_ok, latex_structure_valid
from backend.math.stroke_order import normalize_paths_json_stroke_order
from backend.math.sympy_repair import apply_repair_pipeline, sympy_parseable
from scripts.eval_ocr_cdm import cdm_score


def test_bracket_balance():
    assert bracket_balance_ok(r"\frac{a}{b}")
    assert not bracket_balance_ok(r"\frac{a}{b")


def test_latex_structure_valid():
    ok, _ = latex_structure_valid(r"x+2")
    assert ok
    ok2, reason = latex_structure_valid(r"\frac{")
    assert not ok2
    assert reason == "bracket_mismatch"


def test_repair_latex_strips_empty_frac():
    assert repair_latex(r"a  b") == "a b"


def test_sympy_parseable_arith():
    ok, tag = sympy_parseable("2+3")
    assert ok
    assert tag == "arith"


def test_sympy_repair_uses_alternate():
    out = apply_repair_pipeline(
        r"\frac{",
        0.4,
        "texteller",
        alternate_latex="x+1",
        alternate_confidence=0.7,
        alternate_source="unimernet",
    )
    assert out.latex == "x+1"
    assert out.repaired
    assert "alternate" in out.repair_reason


def test_stroke_order_sorts_top_to_bottom():
    paths = [
        {"drawMode": True, "paths": [{"x": 10, "y": 80}, {"x": 20, "y": 80}]},
        {"drawMode": True, "paths": [{"x": 10, "y": 10}, {"x": 20, "y": 10}]},
    ]
    out = normalize_paths_json_stroke_order(json.dumps(paths))
    parsed = json.loads(out or "[]")
    assert parsed[0]["paths"][0]["y"] == 10


def test_cdm_score_exact():
    assert cdm_score(r"x+2", r"x+2") == 1.0


def test_unimernet_availability_without_artifacts():
    from backend.math.unimernet_onnx import unimernet_artifacts_present, unimernet_available

    assert unimernet_artifacts_present() is False
    assert unimernet_available() is False
