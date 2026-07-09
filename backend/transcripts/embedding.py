"""Shared sentence-transformer helpers for transcript grouping."""

from __future__ import annotations

import importlib.util
import logging
import os
import pickle
import subprocess
import sys
import tempfile
import threading
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import numpy as np

log = logging.getLogger(__name__)

_MODEL = None
_DEFAULT_MODEL = "all-MiniLM-L6-v2"
_PACKAGE_AVAILABLE: bool | None = None
_REPO_ROOT = Path(__file__).resolve().parents[2]


def _tk_root_exists() -> bool:
    try:
        import tkinter

        return tkinter._default_root is not None  # type: ignore[attr-defined]
    except Exception:
        return False


def _prefer_subprocess_encode() -> bool:
    """Torch/sentence-transformers in a worker thread while Tk runs crashes on Windows."""
    forced = os.environ.get("EMBED_IN_SUBPROCESS", "").strip().lower()
    if forced in ("0", "false", "no"):
        return False
    if forced in ("1", "true", "yes"):
        return True
    if os.environ.get("TRANSCRIPT_STUDIO_GUI", "").strip().lower() in ("1", "true", "yes"):
        return threading.current_thread() is not threading.main_thread()
    if threading.current_thread() is not threading.main_thread() and _tk_root_exists():
        return True
    return False


def _sentence_transformers_installed() -> bool:
    global _PACKAGE_AVAILABLE
    if _PACKAGE_AVAILABLE is not None:
        return _PACKAGE_AVAILABLE
    try:
        _PACKAGE_AVAILABLE = importlib.util.find_spec("sentence_transformers") is not None
    except Exception:
        _PACKAGE_AVAILABLE = False
    return _PACKAGE_AVAILABLE


def load_model(model_name: str = _DEFAULT_MODEL):
    global _MODEL
    if _prefer_subprocess_encode():
        return None
    if _MODEL is not None:
        return _MODEL
    try:
        from sentence_transformers import SentenceTransformer  # type: ignore

        _MODEL = SentenceTransformer(model_name, device="cpu")
        return _MODEL
    except Exception:
        return None


def is_available() -> bool:
    if _prefer_subprocess_encode():
        return _sentence_transformers_installed()
    return load_model() is not None


def _encode_texts_inprocess(texts: list[str], *, model_name: str = _DEFAULT_MODEL) -> "np.ndarray | None":
    model = load_model(model_name)
    if model is None or not texts:
        return None
    try:
        import numpy as np  # noqa: PLC0415

        parts: list[np.ndarray] = []
        batch_size = 64
        for start in range(0, len(texts), batch_size):
            batch = texts[start : start + batch_size]
            vectors: np.ndarray = model.encode(  # type: ignore[union-attr]
                batch,
                convert_to_numpy=True,
                show_progress_bar=False,
                batch_size=batch_size,
                device="cpu",
            )
            parts.append(vectors.astype("float32"))
        if not parts:
            return None
        return np.vstack(parts)
    except Exception:
        return None


def _encode_texts_subprocess(texts: list[str], *, model_name: str = _DEFAULT_MODEL) -> "np.ndarray | None":
    if not texts:
        return None
    if not _sentence_transformers_installed():
        return None

    inpath = ""
    outpath = ""
    try:
        with tempfile.NamedTemporaryFile("wb", delete=False, suffix=".pkl") as handle:
            pickle.dump({"texts": texts, "model_name": model_name}, handle)
            inpath = handle.name
        outpath = f"{inpath}.npy"

        env = os.environ.copy()
        env.pop("TRANSCRIPT_STUDIO_GUI", None)
        env.setdefault("TOKENIZERS_PARALLELISM", "false")
        env.setdefault("OMP_NUM_THREADS", "1")
        env.setdefault("MKL_NUM_THREADS", "1")

        result = subprocess.run(
            [sys.executable, "-m", "backend.transcripts.embedding_worker", inpath, outpath],
            cwd=str(_REPO_ROOT),
            capture_output=True,
            text=True,
            env=env,
            timeout=600,
        )
        if result.returncode != 0:
            err = (result.stderr or result.stdout or "unknown error").strip()
            log.warning("Embedding subprocess failed: %s", err[:500])
            return None

        import numpy as np  # noqa: PLC0415

        return np.load(outpath)
    except Exception as exc:
        log.warning("Embedding subprocess error: %s", exc)
        return None
    finally:
        for path in (inpath, outpath):
            if not path:
                continue
            try:
                os.unlink(path)
            except OSError:
                pass


def encode_texts(texts: list[str], *, model_name: str = _DEFAULT_MODEL) -> "np.ndarray | None":
    if _prefer_subprocess_encode():
        return _encode_texts_subprocess(texts, model_name=model_name)
    return _encode_texts_inprocess(texts, model_name=model_name)


def cosine_similarity(a: "np.ndarray", b: "np.ndarray") -> float:
    import numpy as np  # noqa: PLC0415

    na, nb = float(np.linalg.norm(a)), float(np.linalg.norm(b))
    if na == 0.0 or nb == 0.0:
        return 0.0
    return float(np.dot(a, b) / (na * nb))


def mean_vector(vectors: "np.ndarray") -> "np.ndarray":
    import numpy as np  # noqa: PLC0415

    if len(vectors) == 0:
        return vectors
    return vectors.mean(axis=0).astype("float32")
