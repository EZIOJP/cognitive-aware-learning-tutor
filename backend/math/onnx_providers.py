"""ONNX Runtime execution provider resolution for math OCR."""

from __future__ import annotations

import logging
import os

logger = logging.getLogger(__name__)

_CUDA = "CUDAExecutionProvider"
_CPU = "CPUExecutionProvider"

_active_provider: str | None = None


def _available_providers() -> list[str]:
    try:
        import onnxruntime as ort

        return list(ort.get_available_providers())
    except ImportError:
        return [_CPU]


def onnx_execution_providers() -> list[str]:
    """
    Provider list for ``InferenceSession(providers=...)``.

    ``OCR_ONNX_DEVICE``:
      ``auto`` (default) — CUDA when available, else CPU
      ``cuda`` — prefer CUDA, fall back to CPU
      ``cpu`` — CPU only
    """
    mode = os.environ.get("OCR_ONNX_DEVICE", "auto").strip().lower()
    available = _available_providers()
    if mode == "cpu":
        return [_CPU]
    if mode in ("auto", "cuda"):
        if _CUDA in available:
            return [_CUDA, _CPU]
        if mode == "cuda":
            logger.warning(
                "OCR_ONNX_DEVICE=cuda but CUDAExecutionProvider unavailable; using CPU"
            )
    return [_CPU]


def primary_onnx_provider() -> str:
    return onnx_execution_providers()[0]


def note_active_provider(provider: str) -> None:
    global _active_provider
    _active_provider = provider


def active_execution_provider() -> str | None:
    """Best-effort provider used after TexTeller/MFD load (None until first load)."""
    return _active_provider
