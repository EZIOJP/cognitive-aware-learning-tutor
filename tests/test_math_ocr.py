"""Unit tests for math OCR helpers (no TexTeller model download required)."""

import base64
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
    prepare_for_texteller,
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
