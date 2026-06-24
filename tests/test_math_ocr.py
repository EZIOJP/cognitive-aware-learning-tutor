"""Unit tests for math OCR helpers (no TexTeller model download required)."""

import base64
import json
from io import BytesIO

import numpy as np
import pytest
from PIL import Image, ImageDraw

from backend.math.ocr_service import (
    _ocr_looks_hallucinated,
    crop_to_content,
    decode_canvas_image,
    flatten_on_white,
    image_has_ink,
    latex_is_complete,
    paths_have_ink,
    prepare_for_texteller,
    synthesize_from_paths,
    texteller_available,
    recognize_canvas,
)


def _png_data_url(draw_fn) -> str:
    img = Image.new("RGB", (200, 120), "white")
    draw_fn(ImageDraw.Draw(img))
    buf = BytesIO()
    img.save(buf, format="PNG")
    b64 = base64.b64encode(buf.getvalue()).decode("ascii")
    return f"data:image/png;base64,{b64}"


def test_decode_canvas_image():
    url = _png_data_url(lambda d: d.line([(10, 60), (180, 60)], fill="black", width=3))
    img = decode_canvas_image(url)
    assert img.size == (200, 120)


def test_image_has_ink_blank():
    url = _png_data_url(lambda d: None)
    img = decode_canvas_image(url)
    assert not image_has_ink(img)


def test_image_has_ink_stroke():
    url = _png_data_url(lambda d: d.line([(10, 60), (180, 60)], fill="black", width=4))
    img = decode_canvas_image(url)
    assert image_has_ink(img)


def test_flatten_on_white():
    img = Image.new("RGBA", (40, 40), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.ellipse((10, 10, 30, 30), fill=(0, 0, 0, 255))
    flat = flatten_on_white(img)
    assert flat.mode == "RGB"
    assert np.mean(np.array(flat)) > 195


def test_prepare_for_texteller_upscales():
    img = Image.new("RGB", (20, 20), (255, 255, 255))
    d = ImageDraw.Draw(img)
    d.ellipse((6, 6, 14, 14), fill="black")
    out = prepare_for_texteller(img)
    assert min(out.size) >= 128


def test_texteller_stack_import():
    """Import smoke — does not download weights."""
    from backend.math.texteller_onnx import strip_latex_delimiters

    assert strip_latex_delimiters(r"\[x+2\]") == "x+2"
    _ = texteller_available()


def test_crop_to_content():
    url = _png_data_url(lambda d: d.rectangle((50, 40, 150, 80), outline="black", width=2))
    img = decode_canvas_image(url)
    cropped, changed = crop_to_content(img)
    assert changed
    assert cropped.size[0] <= img.size[0]


def test_ocr_looks_hallucinated_table_noise():
    assert _ocr_looks_hallucinated(r"\begin{array}{|c|c|}\hline\end{array}")
    assert _ocr_looks_hallucinated(r"\hat{j}")
    assert not _ocr_looks_hallucinated("3")
    assert not _ocr_looks_hallucinated(r"x^2+1")


def test_latex_is_complete():
    assert latex_is_complete(r"x^2 + 1")
    assert not latex_is_complete(r"\frac{a}{")
    assert not latex_is_complete("")


def test_recognize_canvas_empty_raises():
    url = _png_data_url(lambda d: None)
    with pytest.raises(ValueError, match="empty"):
        recognize_canvas(url)


def test_synthesize_from_paths_draws_ink():
    paths = json.dumps(
        [
            {
                "paths": [{"x": 20, "y": 60}, {"x": 180, "y": 60}],
                "strokeWidth": 4,
                "strokeColor": "#000000",
                "drawMode": True,
            }
        ]
    )
    assert paths_have_ink(paths)
    img = synthesize_from_paths(paths, (200, 120))
    assert img is not None
    assert image_has_ink(img)


def test_recognize_canvas_blank_png_with_paths():
    """MathGridCanvas transparent exports can be blank; paths_json must rescue OCR."""
    url = _png_data_url(lambda d: None)
    paths = json.dumps(
        [
            {
                "paths": [{"x": 20, "y": 60}, {"x": 180, "y": 60}],
                "strokeWidth": 4,
                "strokeColor": "#000000",
                "drawMode": True,
            }
        ]
    )
    if not texteller_available():
        pytest.skip("TexTeller ONNX not installed")
    result = recognize_canvas(url, paths_json=paths, ollama_vision_fallback=False)
    assert result.tier in ("texteller", "contour", "per_cell", "texteller_rejected", "tier3_empty")


def test_recognize_canvas_without_texteller():
    url = _png_data_url(lambda d: d.line([(20, 60), (160, 60)], fill="black", width=4))
    try:
        result = recognize_canvas(url, ollama_vision_fallback=False)
    except ImportError:
        pytest.skip("TexTeller ONNX not installed")
    except RuntimeError as e:
        if "inference failed" in str(e).lower():
            pytest.skip("TexTeller model not cached")
        raise
    assert result.incomplete_step is not None


def test_mask_from_paths():
    from backend.math.ocr_service import mask_from_paths

    url = _png_data_url(lambda d: d.line([(20, 60), (160, 60)], fill="black", width=4))
    img = decode_canvas_image(url)
    masked = mask_from_paths(img, "[]")
    assert masked.size == img.size


def test_recognize_canvas_never_returns_table_noise():
    """Golden guard: simple strokes must not produce \\begin{array} hallucinations."""
    from backend.math.ocr_service import _ocr_looks_hallucinated

    url = _png_data_url(
        lambda d: d.line([(60, 30), (140, 30), (140, 60), (60, 60), (60, 90), (140, 90)], fill="black", width=5)
    )
    if not texteller_available():
        pytest.skip("TexTeller ONNX not installed")
    result = recognize_canvas(url, ollama_vision_fallback=False)
    assert not _ocr_looks_hallucinated(result.latex or "x") or result.latex == ""
    assert r"\begin{array}" not in (result.latex or "")
    assert result.tier in ("texteller", "contour", "per_cell", "texteller_rejected", "tier3_empty")


def test_training_sample_logs_paths_and_target(tmp_path, monkeypatch):
    import backend.math.training_log as tl

    monkeypatch.setattr(tl, "DATASET_CSV", tmp_path / "dataset.csv")
    monkeypatch.setattr(tl, "KINEMATICS_CSV", tmp_path / "kinematics.csv")
    monkeypatch.setattr(tl, "TRAINING_DIR", tmp_path)
    monkeypatch.setattr(tl, "LOG_DIR", tmp_path)

    url = _png_data_url(lambda d: d.line([(20, 60), (160, 60)], fill="black", width=4))
    sample_id = tl.log_training_sample(
        user_id=1,
        tier="digits",
        prompt_id="d3",
        prompt_text="3",
        canvas_image=url,
        predicted_latex="3",
        confirmed_latex="3",
        action="confirm",
        paths_json='[{"paths":[{"x":1,"y":2}],"strokeWidth":3}]',
        target_latex="3",
    )
    assert (tmp_path / f"{sample_id}.paths.json").exists()

    import csv as _csv

    with open(tmp_path / "dataset.csv", newline="", encoding="utf-8") as f:
        rows = list(_csv.DictReader(f))
    assert rows[0]["target_latex"] == "3"
    assert rows[0]["match_predicted"] == "true"
    assert rows[0]["paths_json_path"].endswith(".paths.json")
