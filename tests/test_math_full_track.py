"""Tests for MFD helper geometry, stroke-symbol classifier, and SRS bridge skip rules."""

from __future__ import annotations

import numpy as np
from PIL import Image, ImageDraw

from backend.math.mfd_onnx import _nms, _xywh_to_xyxy, boxes_to_line_bands, mfd_available
from backend.math.srs_bridge import should_skip_srs
from backend.math.stroke_symbol import (
    maybe_disambiguate_latex,
    predict_symbol,
    strokes_to_sequence,
    train_and_save,
)
from backend.math.structure_verify import STRUCTURAL_SILENCE_THRESHOLD


def test_xywh_to_xyxy():
    x0, y0, x1, y1 = _xywh_to_xyxy(50, 50, 20, 10)
    assert abs(x0 - 40) < 1e-6
    assert abs(y1 - 55) < 1e-6


def test_nms_keeps_best():
    boxes = [[0, 0, 10, 10], [1, 1, 11, 11], [50, 50, 60, 60]]
    scores = [0.9, 0.5, 0.8]
    keep = _nms(boxes, scores, 0.3)
    assert 0 in keep
    assert 2 in keep
    assert 1 not in keep


def test_boxes_to_line_bands():
    bands = boxes_to_line_bands(
        [{"x": 10, "y": 20, "w": 100, "h": 30, "score": 0.9, "class_id": 0}]
    )
    assert len(bands) == 1
    assert bands[0].source == "mfd"
    assert bands[0].y0 == 20


def test_mfd_available_is_bool():
    assert isinstance(mfd_available(), bool)


def test_stroke_symbol_train_and_predict(tmp_path, monkeypatch):
    import backend.math.stroke_symbol as ss

    model_path = tmp_path / "model.npz"
    monkeypatch.setattr(ss, "MODEL_PATH", model_path)
    ss._load_model.cache_clear()
    info = train_and_save(model_path, n_per_class=20)
    assert model_path.exists()
    assert info["accuracy"] >= 0.7

    # Horizontal stroke should lean toward "-" or similar
    strokes = [[(0.1, 0.5), (0.9, 0.5)]]
    pred = predict_symbol(strokes, min_confidence=0.2)
    assert pred is not None
    label, conf = pred
    assert label in info["classes"]
    assert conf > 0


def test_maybe_disambiguate_leaves_long_latex():
    latex, conf, src, _needs_review = maybe_disambiguate_latex(
        r"x^2+3x+1",
        confidence=0.2,
        paths_json=None,
    )
    assert latex == r"x^2+3x+1"
    assert src == "ocr"


def test_srs_skip_rules():
    assert should_skip_srs(confidence=0.2, structural_confidence=0.9, tutor_silent=False)
    assert should_skip_srs(
        confidence=0.9,
        structural_confidence=STRUCTURAL_SILENCE_THRESHOLD - 0.1,
        tutor_silent=False,
    )
    assert should_skip_srs(confidence=0.9, structural_confidence=0.9, tutor_silent=True)
    assert not should_skip_srs(confidence=0.9, structural_confidence=0.9, tutor_silent=False)


def test_apply_crop_bbox():
    from backend.math.ocr_service import apply_crop_bbox
    from PIL import Image, ImageDraw

    img = Image.new("RGB", (200, 160), "white")
    d = ImageDraw.Draw(img)
    d.rectangle((20, 20, 80, 60), fill="black")
    d.rectangle((20, 100, 80, 140), fill="black")
    cropped = apply_crop_bbox(img, {"x": 10, "y": 90, "w": 90, "h": 60}, pad=0)
    assert cropped.size[1] <= 70
    assert cropped.size[0] <= 100


def test_apply_crop_bbox_invalid_noop():
    from backend.math.ocr_service import apply_crop_bbox
    from PIL import Image

    img = Image.new("RGB", (40, 40), "white")
    assert apply_crop_bbox(img, None).size == (40, 40)
    assert apply_crop_bbox(img, {"x": 0, "y": 0, "w": 0, "h": 10}).size == (40, 40)


def test_strokes_to_sequence_shape():
    seq = strokes_to_sequence([[(0, 0), (1, 1), (2, 0)]])
    assert seq.shape == (64, 3)
