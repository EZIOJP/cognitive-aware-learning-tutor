"""UniMERNet-T ONNX optional backend (Phase 1).

Requires:
  - ONNX artifacts under data/math/unimernet/artifacts/
  - tokenizer.json under data/math/unimernet/models/unimernet_tiny/
  - pure_onnx_unimernet.py (from torvexlabs/unimernet-onnx) on PYTHONPATH or vendored

See scripts/install_unimernet.bat
"""

from __future__ import annotations

import importlib.util
import logging
import os
from functools import lru_cache
from pathlib import Path
from typing import Any

from PIL import Image

from backend.math.onnx_providers import onnx_execution_providers
from backend.paths import ROOT

logger = logging.getLogger(__name__)

_IMPORT_ERROR: str | None = None

DEFAULT_ARTIFACTS = ROOT / "data" / "math" / "unimernet" / "artifacts"
DEFAULT_TOKENIZER = ROOT / "data" / "math" / "unimernet" / "models" / "unimernet_tiny"


def artifacts_dir() -> Path:
    return Path(os.getenv("UNIMERNET_ARTIFACTS_DIR", str(DEFAULT_ARTIFACTS)))


def tokenizer_dir() -> Path:
    return Path(os.getenv("UNIMERNET_TOKENIZER_DIR", str(DEFAULT_TOKENIZER)))


def unimernet_artifacts_present() -> bool:
    ad = artifacts_dir()
    for name in ("encoder_model.onnx", "decoder_model.onnx", "decoder_with_past_model.onnx"):
        if not (ad / name).is_file():
            return False
    return (tokenizer_dir() / "tokenizer.json").is_file()


def import_error_hint() -> str | None:
    return _IMPORT_ERROR


def _import_unimernet_class() -> type[Any]:
    global _IMPORT_ERROR
    custom = os.getenv("UNIMERNET_PURE_MODULE", "").strip()
    if custom:
        path = Path(custom)
        if not path.is_file():
            raise FileNotFoundError(f"UNIMERNET_PURE_MODULE not found: {path}")
        spec = importlib.util.spec_from_file_location("pure_onnx_unimernet", path)
        if spec is None or spec.loader is None:
            raise ImportError(f"Cannot load module from {path}")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod.OnnxUnimerNet  # type: ignore[attr-defined]
    try:
        from pure_onnx_unimernet import OnnxUnimerNet  # type: ignore[import-not-found]

        return OnnxUnimerNet
    except ImportError:
        pass
    try:
        from backend.math.pure_onnx_unimernet import OnnxUnimerNet

        return OnnxUnimerNet
    except ImportError as e:
        _IMPORT_ERROR = str(e)
        raise ImportError(
            "pure_onnx_unimernet not found. Run scripts/install_unimernet.bat "
            "or set UNIMERNET_PURE_MODULE to pure_onnx_unimernet.py"
        ) from e


def unimernet_available() -> bool:
    """True when artifacts + runtime module are loadable."""
    if not unimernet_artifacts_present():
        return False
    try:
        import onnxruntime  # noqa: F401

        _load_engine()
        return True
    except Exception as e:
        global _IMPORT_ERROR
        _IMPORT_ERROR = str(e)
        return False


@lru_cache(maxsize=1)
def _load_engine() -> Any:
    Cls = _import_unimernet_class()
    providers = onnx_execution_providers()
    engine = Cls(
        artifacts_dir=artifacts_dir(),
        tokenizer_path=tokenizer_dir(),
        providers=providers,
    )
    logger.info("UniMERNet-T ONNX loaded from %s", artifacts_dir())
    return engine


def reload_unimernet_stack() -> dict[str, str | bool]:
    _load_engine.cache_clear()
    return {"artifacts_dir": str(artifacts_dir()), "available": unimernet_available()}


def recognize_image(img: Image.Image) -> str:
    """Run UniMERNet on a PIL crop (RGB/grayscale). Returns LaTeX string."""
    engine = _load_engine()
    out = engine.recognize(img)
    if isinstance(out, dict):
        return str(out.get("latex") or "").strip()
    return str(out).strip()
