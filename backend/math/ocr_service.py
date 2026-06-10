"""
Handwritten math OCR: decode canvas PNG, OpenCV crop, TexTeller ONNX LaTeX, multi-tier fallback.
Optional dependency — install with: pip install -r backend/requirements-ocr.txt

Python 3.14: TexTeller ONNX replaces pix2tex (pix2tex/stringzilla wheels unavailable).
"""

from __future__ import annotations

import base64
import json
import re
from dataclasses import dataclass
from io import BytesIO

import cv2
import numpy as np
from PIL import Image

CONFIDENCE_INCOMPLETE_THRESHOLD = 0.3


def texteller_available() -> bool:
    from backend.math.texteller_onnx import texteller_available as _avail

    return _avail()


def pix2tex_available() -> bool:
    """Deprecated alias — TexTeller replaces pix2tex on Python 3.14+."""
    return texteller_available()


def decode_canvas_image(canvas_image: str) -> Image.Image:
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


def mask_from_paths(img: Image.Image, paths_json: str | None) -> Image.Image:
    """Isolate ink from react-sketch-canvas paths JSON — reduces background noise."""
    if not paths_json or not paths_json.strip():
        return img
    try:
        paths = json.loads(paths_json)
    except (json.JSONDecodeError, TypeError):
        return img
    if not isinstance(paths, list):
        return img

    arr = np.array(img.convert("RGB"))
    mask = np.zeros(arr.shape[:2], dtype=np.uint8)
    for path in paths:
        if not isinstance(path, dict):
            continue
        pts = path.get("paths") or []
        stroke = max(1, int(path.get("strokeWidth") or 3))
        coords: list[tuple[int, int]] = []
        for p in pts:
            if isinstance(p, dict) and "x" in p and "y" in p:
                coords.append((int(p["x"]), int(p["y"])))
        if len(coords) >= 2:
            for i in range(len(coords) - 1):
                cv2.line(mask, coords[i], coords[i + 1], 255, stroke)
        elif len(coords) == 1:
            cv2.circle(mask, coords[0], stroke, 255, -1)

    if int(mask.sum()) == 0:
        return img
    white = np.full_like(arr, 255)
    white[mask > 0] = arr[mask > 0]
    return Image.fromarray(white)


def image_has_ink(img: Image.Image, min_ink_pixels: int = 80) -> bool:
    arr = np.array(img.convert("L"))
    ink = np.sum(arr < 200)
    return int(ink) >= min_ink_pixels


def flatten_on_white(img: Image.Image) -> Image.Image:
    if img.mode == "RGBA":
        base = Image.new("RGB", img.size, (255, 255, 255))
        base.paste(img, mask=img.split()[3])
        return base
    rgb = img.convert("RGB")
    arr = np.array(rgb)
    if float(np.mean(arr)) < 120:
        arr = 255 - arr
        return Image.fromarray(arr)
    return rgb


def _suppress_grid_lines(gray: np.ndarray, *, luma_floor: int = 200) -> np.ndarray:
    """Treat faint ruled/grid pixels as white so they are not fed to TexTeller."""
    out = gray.copy()
    out[out >= luma_floor] = 255
    return out


def prepare_for_texteller(img: Image.Image, *, upscale_if_height_below: int = 64) -> Image.Image:
    """CLAHE + thicken strokes; upscale only when crop height < 64px (ironclad heuristic)."""
    rgb = np.array(flatten_on_white(img))
    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    gray = _suppress_grid_lines(gray)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    gray = clahe.apply(gray)
    _, ink = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    kernel = np.ones((3, 3), np.uint8)
    ink = cv2.dilate(ink, kernel, iterations=1)
    out = np.full((*ink.shape, 3), 255, dtype=np.uint8)
    out[ink > 0] = (0, 0, 0)
    h, w = out.shape[:2]
    if h < upscale_if_height_below:
        min_side = 128
        scale = max(1, int(np.ceil(min_side / max(min(h, w), 1))))
        if scale > 1:
            out = cv2.resize(out, (w * scale, h * scale), interpolation=cv2.INTER_CUBIC)
    pad = max(24, int(0.25 * max(out.shape[0], out.shape[1])))
    out = cv2.copyMakeBorder(out, pad, pad, pad, pad, cv2.BORDER_CONSTANT, value=(255, 255, 255))
    return Image.fromarray(out)


def prepare_for_pix2tex(img: Image.Image, min_side: int = 128) -> Image.Image:
    return prepare_for_texteller(img, upscale_if_height_below=min_side)


def crop_to_content(img: Image.Image, padding: int = 16) -> tuple[Image.Image, bool]:
    rgb = np.array(img.convert("RGB"))
    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    gray = _suppress_grid_lines(gray)
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
    t = latex.replace(" ", "")
    if not t:
        return True
    has_digit = any(c.isdigit() for c in t)
    table_noise = (
        r"\begin{array}",
        r"\begin{matrix}",
        r"\begin{pmatrix}",
        r"\left(\begin",
        r"\hline",
        r"\vphantom",
    )
    if any(s in t for s in table_noise):
        return True
    heavy = (
        r"\mathbb",
        r"\mathsf",
        r"\supset",
        r"\subset",
        r"\setminus",
        r"\Longrightarrow",
        r"\widehat",
        r"\mathcal",
        r"\mathfrak",
        r"\hat{",
    )
    return any(s in t for s in heavy) and not has_digit


def try_contour_digit_latex(img: Image.Image) -> str | None:
    arr = np.array(prepare_for_texteller(img, upscale_if_height_below=64))
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
    parts: list[str] = []
    for _x, _y, w, h, circ in blobs:
        if circ > 0.35 or (0.5 < w / max(h, 1) < 1.8):
            parts.append("0")
        elif h > w * 1.5:
            parts.append("1")
        else:
            return None
    return " ".join(parts) if parts else None


def _ollama_vision_latex(canvas_image: str) -> str | None:
    """Tier 2: Ollama vision model image → LaTeX."""
    import os

    from backend.math.ollama_tutor import ollama_available

    base = ollama_available()
    vision = os.getenv("OLLAMA_VISION_MODEL", "").strip()
    if not base or not vision:
        return None
    import httpx

    raw = canvas_image.split(",", 1)[-1] if "," in canvas_image else canvas_image
    payload = {
        "model": vision,
        "messages": [
            {
                "role": "user",
                "content": "Transcribe the handwritten math as LaTeX only. No explanation.",
                "images": [raw],
            }
        ],
        "stream": False,
        "keep_alive": -1,
    }
    try:
        with httpx.Client(timeout=60.0) as client:
            res = client.post(f"{base}/api/chat", json=payload)
            res.raise_for_status()
            raw_out = res.json().get("message", {}).get("content", "")
        text = (raw_out or "").strip().strip("$").strip()
        return text or None
    except Exception:
        return None


def _nim_teacher_latex(canvas_image: str) -> tuple[str, bool]:
    """Tier 0 (opt-in): NIM vision teacher label. Returns (latex, needs_review)."""
    from backend.integrations.nim_client import nim_available, nim_vision_latex_sync

    if not nim_available():
        return "", False
    try:
        label = nim_vision_latex_sync(canvas_image).strip()
        return label, False
    except Exception:
        return "", True


def _run_texteller(prepared: Image.Image) -> str:
    from backend.math.texteller_onnx import recognize_image

    return recognize_image(prepared).strip()


def _finalize_result(
    latex: str,
    *,
    preprocess_applied: bool,
    used_simple: bool,
    teacher_latex: str = "",
) -> OcrResult:
    if not latex:
        return OcrResult(
            latex="",
            incomplete_step=True,
            confidence=0.0,
            preprocess_applied=preprocess_applied,
            teacher_latex=teacher_latex,
            needs_review=bool(teacher_latex),
        )

    complete = latex_is_complete(latex)
    confidence = 0.85 if used_simple else (1.0 if complete else 0.45)
    if teacher_latex and teacher_latex.strip() == latex.strip():
        confidence = min(1.0, confidence + 0.3)
    incomplete = not complete or confidence < CONFIDENCE_INCOMPLETE_THRESHOLD
    needs_review = bool(teacher_latex and teacher_latex.strip() != latex.strip())
    return OcrResult(
        latex=latex,
        incomplete_step=incomplete,
        confidence=confidence,
        preprocess_applied=preprocess_applied,
        teacher_latex=teacher_latex,
        needs_review=needs_review,
    )


@dataclass
class OcrResult:
    latex: str
    incomplete_step: bool
    confidence: float
    preprocess_applied: bool
    teacher_latex: str = ""
    needs_review: bool = False
    tier: str = "texteller"


def recognize_canvas(
    canvas_image: str,
    *,
    paths_json: str | None = None,
    ollama_vision_fallback: bool = True,
    use_nim_teacher: bool = True,
) -> OcrResult:
    """
    Multi-tier pipeline:
    Tier 0 (opt-in NIM): teacher label stored alongside prediction
    Tier 1: TexTeller ONNX
    Tier 2: Ollama vision (if enabled + incomplete)
    Tier 3: empty latex + incomplete_step (never hard-fails)
    """
    img = flatten_on_white(decode_canvas_image(canvas_image))
    if not image_has_ink(img):
        raise ValueError("Canvas appears empty — draw an equation first.")

    teacher_latex = ""
    needs_review = False
    if use_nim_teacher:
        teacher_latex, needs_review = _nim_teacher_latex(canvas_image)

    img = mask_from_paths(img, paths_json)
    cropped, crop_applied = crop_to_content(img)
    prepared = prepare_for_texteller(cropped)
    preprocess_applied = crop_applied or True
    simple_latex = try_contour_digit_latex(cropped)

    latex = ""
    tier = "none"

    if texteller_available():
        try:
            latex = _run_texteller(prepared)
            tier = "texteller"
        except Exception:
            latex = ""
    else:
        # No OCR engine — Tier 3 immediately with rule-tutor-safe empty latex
        return OcrResult(
            latex="",
            incomplete_step=True,
            confidence=0.0,
            preprocess_applied=preprocess_applied,
            teacher_latex=teacher_latex,
            needs_review=needs_review,
            tier="unavailable",
        )

    if _ocr_looks_hallucinated(latex):
        if simple_latex:
            latex = simple_latex
            tier = "contour"
        else:
            latex = ""
            tier = "texteller_rejected"

    result = _finalize_result(
        latex,
        preprocess_applied=preprocess_applied,
        used_simple=bool(simple_latex and latex == simple_latex),
        teacher_latex=teacher_latex,
    )
    result.tier = tier

    if result.incomplete_step and ollama_vision_fallback:
        alt = _ollama_vision_latex(canvas_image)
        if alt:
            alt_result = _finalize_result(
                alt,
                preprocess_applied=preprocess_applied,
                used_simple=False,
                teacher_latex=teacher_latex,
            )
            alt_result.tier = "ollama_vision"
            if alt_result.confidence >= result.confidence or not result.latex:
                return alt_result

    if not result.latex:
        result.tier = "tier3_empty"
    return result
