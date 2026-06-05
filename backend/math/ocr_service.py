"""
Handwritten math OCR: decode canvas PNG, OpenCV crop, pix2tex LaTeX, SymPy validation.
Optional dependency — install with: pip install -r backend/requirements-ocr.txt
"""

from __future__ import annotations

import base64
import re
from dataclasses import dataclass
from io import BytesIO
from typing import Any

import cv2
import numpy as np
from PIL import Image

_OCR_MODEL: Any = None
_PIX2TEX_IMPORT_ERROR: str | None = None


def pix2tex_available() -> bool:
    """True if pix2tex and LatexOCR are importable (weights load lazily on first request)."""
    try:
        from pix2tex.cli import LatexOCR  # noqa: F401
        return True
    except ImportError:
        return False


def _get_ocr_model():
    global _OCR_MODEL, _PIX2TEX_IMPORT_ERROR
    if _OCR_MODEL is not None:
        return _OCR_MODEL
    try:
        from pix2tex.cli import LatexOCR

        _OCR_MODEL = LatexOCR()
        return _OCR_MODEL
    except ImportError as e:
        _PIX2TEX_IMPORT_ERROR = str(e)
        raise
    except Exception as e:
        _PIX2TEX_IMPORT_ERROR = str(e)
        raise


def decode_canvas_image(canvas_image: str) -> Image.Image:
    """Decode data-URL or raw base64 PNG into RGB PIL Image."""
    raw = canvas_image.strip()
    if "," in raw:
        raw = raw.split(",", 1)[1]
    try:
        data = base64.b64decode(raw, validate=True)
    except Exception as e:
        raise ValueError(f"Invalid base64 image: {e}") from e
    img = Image.open(BytesIO(data))
    if img.mode != "RGB":
        img = img.convert("RGB")
    return img


def image_has_ink(img: Image.Image, min_ink_pixels: int = 80) -> bool:
    """Reject blank or near-blank canvases."""
    arr = np.array(img.convert("L"))
    # Dark strokes on light background
    ink = np.sum(arr < 200)
    return int(ink) >= min_ink_pixels


def flatten_on_white(img: Image.Image) -> Image.Image:
    """Composite RGBA/transparent exports onto white (pix2tex expects black on white)."""
    if img.mode == "RGBA":
        base = Image.new("RGB", img.size, (255, 255, 255))
        base.paste(img, mask=img.split()[3])
        return base
    rgb = img.convert("RGB")
    arr = np.array(rgb)
    # Transparent PNGs often decode as black background — invert if mostly dark
    if float(np.mean(arr)) < 120:
        arr = 255 - arr
        return Image.fromarray(arr)
    return rgb


def prepare_for_pix2tex(img: Image.Image, min_side: int = 128) -> Image.Image:
    """
    Thicken thin strokes, enforce black-on-white, upscale small crops, add margin.
    Improves recognition of simple digits (e.g. 0 0) from web canvas exports.
    """
    rgb = np.array(flatten_on_white(img))
    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    _, ink = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    kernel = np.ones((3, 3), np.uint8)
    ink = cv2.dilate(ink, kernel, iterations=1)
    # ink mask: 255 = stroke; output black strokes on white
    out = np.full((*ink.shape, 3), 255, dtype=np.uint8)
    out[ink > 0] = (0, 0, 0)
    h, w = out.shape[:2]
    scale = max(1, int(np.ceil(min_side / max(min(h, w), 1))))
    if scale > 1:
        out = cv2.resize(out, (w * scale, h * scale), interpolation=cv2.INTER_CUBIC)
    pad = max(24, int(0.25 * max(out.shape[0], out.shape[1])))
    out = cv2.copyMakeBorder(out, pad, pad, pad, pad, cv2.BORDER_CONSTANT, value=(255, 255, 255))
    return Image.fromarray(out)


def crop_to_content(img: Image.Image, padding: int = 16) -> tuple[Image.Image, bool]:
    """
    Grayscale threshold + bounding box of ink; returns cropped image and whether crop changed bounds.
    """
    rgb = np.array(img.convert("RGB"))
    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    coords = cv2.findNonZero(binary)
    if coords is None:
        return img, False
    x, y, w, h = cv2.boundingRect(coords)
    H, W = gray.shape
    x0 = max(0, x - padding)
    y0 = max(0, y - padding)
    x1 = min(W, x + w + padding)
    y1 = min(H, y + h + padding)
    if x1 <= x0 or y1 <= y0:
        return img, False
    cropped = rgb[y0:y1, x0:x1]
    changed = (x0, y0, x1, y1) != (0, 0, W, H)
    return Image.fromarray(cropped), changed


def _balance_ok(s: str) -> bool:
    pairs = {"(": ")", "{": "}", "[": "]"}
    stack: list[str] = []
    for ch in s:
        if ch in pairs:
            stack.append(pairs[ch])
        elif ch in pairs.values():
            if not stack or stack.pop() != ch:
                return False
    return len(stack) == 0


def latex_is_complete(latex: str) -> bool:
    """
    SymPy LaTeX parse when antlr is available; else bracket balance + sympify fallback.
    """
    text = (latex or "").strip()
    if not text:
        return False
    if re.fullmatch(r"[\d\s.+\-*/=()]+", text):
        return True
    if not _balance_ok(text):
        return False
    if re.search(r"(\\frac\{[^}]*\}\s*$|^\s*\\frac\s*$|[+\-*/=]\s*$)", text):
        return False
    try:
        from sympy.parsing.latex import parse_latex

        parse_latex(text)
        return True
    except Exception:
        pass
    try:
        import sympy

        expr = text
        for tok in (r"\cdot", r"\times", r"\div"):
            expr = expr.replace(tok, "*")
        expr = expr.replace("^", "**")
        sympy.sympify(expr)
        return True
    except Exception:
        return False


def _ocr_looks_hallucinated(latex: str) -> bool:
    """Heuristic: model invented set theory symbols with no digits."""
    t = latex.replace(" ", "")
    if not t:
        return True
    has_digit = any(c.isdigit() for c in t)
    heavy = (
        r"\mathbb",
        r"\mathsf",
        r"\supset",
        r"\subset",
        r"\setminus",
        r"\Longrightarrow",
        r"\Longrightarrow",
    )
    return any(s in t for s in heavy) and not has_digit


def try_contour_digit_latex(img: Image.Image) -> str | None:
    """
    Fast path for a few separated round strokes (e.g. two zeros).
    Returns space-separated digits or None if layout is not simple enough.
    """
    arr = np.array(prepare_for_pix2tex(img, min_side=64))
    gray = cv2.cvtColor(arr, cv2.COLOR_RGB2GRAY)
    _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    blobs: list[tuple[int, int, int, int, float]] = []
    H, W = gray.shape
    min_area = max(80, (H * W) * 0.0005)
    for c in contours:
        x, y, w, h = cv2.boundingRect(c)
        area = w * h
        if area < min_area:
            continue
        aspect = w / max(h, 1)
        if aspect < 0.35 or aspect > 2.8:
            continue
        circularity = 4 * np.pi * area / max(cv2.arcLength(c, True) ** 2, 1)
        blobs.append((x, y, w, h, circularity))
    if not blobs or len(blobs) > 6:
        return None
    blobs.sort(key=lambda b: b[0])
    # Round blobs → 0; short wide strokes → 1 (optional)
    parts: list[str] = []
    for _x, _y, w, h, circ in blobs:
        if circ > 0.35 or (0.5 < w / max(h, 1) < 1.8):
            parts.append("0")
        elif h > w * 1.5:
            parts.append("1")
        else:
            return None
    if not parts:
        return None
    return " ".join(parts)


@dataclass
class OcrResult:
    latex: str
    incomplete_step: bool
    confidence: float
    preprocess_applied: bool


def recognize_canvas(canvas_image: str) -> OcrResult:
    """
    Full pipeline: decode → ink check → crop → pix2tex → validate.
    Raises ImportError if pix2tex not installed.
    Raises ValueError for empty/invalid image.
    """
    img = flatten_on_white(decode_canvas_image(canvas_image))
    if not image_has_ink(img):
        raise ValueError("Canvas appears empty — draw an equation first.")

    if not pix2tex_available():
        hint = _PIX2TEX_IMPORT_ERROR or "pix2tex not installed"
        raise ImportError(
            f"Math OCR unavailable ({hint}). "
            "Run scripts\\install_ocr.bat or see backend/requirements-ocr.txt"
        )

    cropped, crop_applied = crop_to_content(img)
    prepared = prepare_for_pix2tex(cropped)
    preprocess_applied = crop_applied or True

    simple_latex = try_contour_digit_latex(cropped)
    model = _get_ocr_model()
    latex = (model(prepared) or "").strip()
    if simple_latex and (_ocr_looks_hallucinated(latex) or not latex):
        latex = simple_latex

    if not latex:
        return OcrResult(
            latex="",
            incomplete_step=True,
            confidence=0.0,
            preprocess_applied=preprocess_applied,
        )

    complete = latex_is_complete(latex)
    used_simple = simple_latex and latex == simple_latex
    confidence = 0.85 if used_simple else (1.0 if complete else 0.45)
    return OcrResult(
        latex=latex,
        incomplete_step=not complete,
        confidence=confidence,
        preprocess_applied=preprocess_applied,
    )
