"""Shared sentence-transformer helpers for transcript grouping."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import numpy as np

_MODEL = None
_DEFAULT_MODEL = "all-MiniLM-L6-v2"


def load_model(model_name: str = _DEFAULT_MODEL):
    global _MODEL
    if _MODEL is not None:
        return _MODEL
    try:
        from sentence_transformers import SentenceTransformer  # type: ignore

        _MODEL = SentenceTransformer(model_name, device="cpu")
        return _MODEL
    except Exception:
        return None


def is_available() -> bool:
    return load_model() is not None


def encode_texts(texts: list[str], *, model_name: str = _DEFAULT_MODEL) -> "np.ndarray | None":
    model = load_model(model_name)
    if model is None or not texts:
        return None
    if len(texts) > 256:
        texts = texts[:256]
    try:
        import numpy as np  # noqa: PLC0415

        vectors: np.ndarray = model.encode(  # type: ignore[union-attr]
            texts,
            convert_to_numpy=True,
            show_progress_bar=False,
            batch_size=64,
            device="cpu",
        )
        return vectors.astype("float32")
    except Exception:
        return None


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
