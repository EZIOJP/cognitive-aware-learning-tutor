"""
TexTeller ONNX inference — CPU only (CPUExecutionProvider).

Uses Ji-Ha/TexTeller3-ONNX-dynamic via optimum.onnxruntime (no pix2tex / PyTorch GPU).
Model downloads on first request (~1GB) into HF cache or TEXTELLER_CACHE_DIR.
"""

from __future__ import annotations

import os
import re
from functools import lru_cache
from typing import Any

import numpy as np
from PIL import Image

_IMPORT_ERROR: str | None = None
_DEFAULT_MODEL = os.environ.get("TEXTELLER_MODEL_ID", "Ji-Ha/TexTeller3-ONNX-dynamic")


def texteller_available() -> bool:
    """True when onnxruntime + optimum + transformers can load the ONNX model."""
    try:
        import onnxruntime  # noqa: F401
        from optimum.onnxruntime import ORTModelForVision2Seq  # noqa: F401
        from transformers import AutoImageProcessor, AutoTokenizer  # noqa: F401
        return True
    except ImportError:
        return False


def _cache_dir() -> str | None:
    path = os.environ.get("TEXTELLER_CACHE_DIR", "").strip()
    return path or None


@lru_cache(maxsize=1)
def _load_stack(model_id: str = _DEFAULT_MODEL) -> tuple[Any, Any, Any]:
    global _IMPORT_ERROR
    try:
        from optimum.onnxruntime import ORTModelForVision2Seq
        from transformers import AutoImageProcessor, AutoTokenizer

        kwargs: dict[str, Any] = {
            "provider": "CPUExecutionProvider",
            "export": False,
        }
        cache = _cache_dir()
        if cache:
            kwargs["cache_dir"] = cache

        model = ORTModelForVision2Seq.from_pretrained(model_id, **kwargs)
        image_processor = AutoImageProcessor.from_pretrained(model_id, cache_dir=cache)
        tokenizer = AutoTokenizer.from_pretrained(model_id, cache_dir=cache)
        return model, image_processor, tokenizer
    except ImportError as e:
        _IMPORT_ERROR = str(e)
        raise
    except Exception as e:
        _IMPORT_ERROR = str(e)
        raise


def import_error_hint() -> str | None:
    return _IMPORT_ERROR


def _pil_to_model_input(img: Image.Image, image_processor: Any) -> Any:
    """Grayscale (H, W, 1) numpy — ViT preprocessor resizes to 448×448."""
    gray = np.array(img.convert("L"), dtype=np.uint8)
    arr = gray[:, :, np.newaxis]
    return image_processor(images=arr, return_tensors="pt").pixel_values


def strip_latex_delimiters(latex: str) -> str:
    text = (latex or "").strip()
    text = re.sub(r"^\$+|\$+$", "", text)
    text = re.sub(r"^\\\[(.*)\\\]$", r"\1", text, flags=re.DOTALL)
    text = re.sub(r"^\\\((.*)\\\)$", r"\1", text, flags=re.DOTALL)
    return text.strip()


def recognize_image(img: Image.Image, *, max_new_tokens: int = 128) -> str:
    """
    Run TexTeller ONNX on a preprocessed PIL image (black ink on white).
    Returns cleaned LaTeX string (may be empty).
    """
    model, image_processor, tokenizer = _load_stack()
    pixel_values = _pil_to_model_input(img, image_processor)
    generated = model.generate(pixel_values=pixel_values, max_new_tokens=max_new_tokens)
    raw = tokenizer.batch_decode(generated, skip_special_tokens=True)[0]
    return strip_latex_delimiters(raw)
