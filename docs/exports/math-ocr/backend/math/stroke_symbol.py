"""
Stroke-sequence isolated-symbol classifier (Track B disambiguator).

Trains / loads a tiny numpy softmax over resampled (dx, dy, pen_up) features.
Used only when TexTeller confidence is low on a simple single-glyph-looking
crop — never replaces the main OCR path.

Retrain on confirmed ink: ``train_from_handwriting_dataset()`` or
``POST /api/math/train/retrain-stroke-symbol``.
"""

from __future__ import annotations

import json
import logging
import math
import random
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

import numpy as np

from backend.paths import ROOT

logger = logging.getLogger(__name__)

SEQ_LEN = 64
FEAT_DIM = 3
HIDDEN = 64
SEED = 42
MODEL_PATH = ROOT / "data" / "math" / "stroke_symbol_model.npz"
LABELS_DEFAULT = ["0", "1", "2", "3", "+", "-", "x", "="]

# LaTeX / unicode → classifier label (short OCR disambiguation output).
_GLYPH_CANONICAL: dict[str, str] = {
    "+": "+",
    "-": "-",
    "=": "=",
    "x": "x",
    "X": "x",
    "−": "-",
    "·": ".",
    "÷": "/",
}

_MULTI_GLYPH_RE = re.compile(
    r"\\frac|\\sqrt|\\begin|\\sum|\\int|\\times|\\div|\\neq|\\leq|\\geq|\^|_|\{|\}"
)


def _jitter(pts, rng, s=0.04):
    return [(x + rng.uniform(-s, s), y + rng.uniform(-s, s)) for x, y in pts]


def _synth_glyphs(n_per: int = 40) -> list[tuple[str, list[list[tuple[float, float]]]]]:
    rng = random.Random(SEED)

    def ellipse():
        pts = [(0.5 + 0.35 * math.cos(t), 0.5 + 0.4 * math.sin(t)) for t in np.linspace(0, 2 * math.pi, 40)]
        return [_jitter(pts, rng)]

    def vline():
        return [_jitter([(0.5, y) for y in np.linspace(0.1, 0.9, 30)], rng)]

    def hline():
        return [_jitter([(x, 0.5) for x in np.linspace(0.15, 0.85, 25)], rng)]

    def plus():
        return [
            _jitter([(x, 0.5) for x in np.linspace(0.2, 0.8, 20)], rng),
            _jitter([(0.5, y) for y in np.linspace(0.2, 0.8, 20)], rng),
        ]

    def equals():
        return [
            _jitter([(x, 0.35) for x in np.linspace(0.2, 0.8, 20)], rng),
            _jitter([(x, 0.65) for x in np.linspace(0.2, 0.8, 20)], rng),
        ]

    def xmark():
        return [
            _jitter([(t, t) for t in np.linspace(0.2, 0.8, 20)], rng),
            _jitter([(t, 1 - t) for t in np.linspace(0.2, 0.8, 20)], rng),
        ]

    def two():
        pts = [(0.25, 0.3), (0.5, 0.15), (0.75, 0.3), (0.7, 0.5), (0.3, 0.85), (0.8, 0.85)]
        dense = []
        for i in range(len(pts) - 1):
            for a in np.linspace(0, 1, 8):
                dense.append(
                    (
                        pts[i][0] * (1 - a) + pts[i + 1][0] * a,
                        pts[i][1] * (1 - a) + pts[i + 1][1] * a,
                    )
                )
        return [_jitter(dense, rng)]

    def three():
        pts = [(0.3, 0.2), (0.7, 0.2), (0.55, 0.5), (0.7, 0.5), (0.7, 0.8), (0.3, 0.8)]
        dense = []
        for i in range(len(pts) - 1):
            for a in np.linspace(0, 1, 8):
                dense.append(
                    (
                        pts[i][0] * (1 - a) + pts[i + 1][0] * a,
                        pts[i][1] * (1 - a) + pts[i + 1][1] * a,
                    )
                )
        return [_jitter(dense, rng)]

    gens = {
        "0": ellipse,
        "1": vline,
        "2": two,
        "3": three,
        "+": plus,
        "-": hline,
        "x": xmark,
        "=": equals,
    }
    out = []
    for label, gen in gens.items():
        for _ in range(n_per):
            out.append((label, gen()))
    return out


def normalize_glyph_label(latex: str) -> str | None:
    """
    Map a confirmed LaTeX string to a single disambiguator class, or None.

    Accepts one digit (0–9) or a single operator/variable glyph.
    """
    text = (latex or "").strip()
    text = re.sub(r"^\$+|\$+$", "", text).strip()
    if not text or len(text) > 3:
        return None
    if _MULTI_GLYPH_RE.search(text):
        return None
    if len(text) == 1 and text.isdigit():
        return text
    if text in _GLYPH_CANONICAL:
        return _GLYPH_CANONICAL[text]
    # Single letter variable (curriculum: x, y, n, …)
    if len(text) == 1 and text.isalpha():
        return text.lower()
    return None


def read_paths_json_for_row(row: dict) -> str | None:
    rel = (row.get("paths_json_path") or "").strip()
    if not rel:
        return None
    path = Path(rel)
    if not path.is_absolute():
        path = ROOT / path
    if not path.is_file():
        return None
    return path.read_text(encoding="utf-8")


def collect_dataset_glyph_samples(
    rows: list[dict] | None = None,
    *,
    user_id: int | None = None,
) -> tuple[list[tuple[str, list[list[tuple[float, float]]]]], dict[str, int]]:
    """Load (label, strokes) from DSC_handwriting_dataset rows with paths_json."""
    if rows is None:
        from backend.math.training_log import _read_rows

        rows = _read_rows(user_id)

    from backend.math.retrain_service import ground_truth_latex

    out: list[tuple[str, list[list[tuple[float, float]]]]] = []
    skip: dict[str, int] = {}

    def _skip(reason: str) -> None:
        skip[reason] = skip.get(reason, 0) + 1

    for row in rows:
        label = normalize_glyph_label(ground_truth_latex(row))
        if not label:
            _skip("not_single_glyph")
            continue
        raw = read_paths_json_for_row(row)
        if not raw:
            _skip("missing_paths_json")
            continue
        strokes = paths_json_to_strokes(raw)
        points = sum(len(s) for s in strokes)
        if len(strokes) < 1 or points < 2:
            _skip("too_few_stroke_points")
            continue
        out.append((label, strokes))

    return out, skip


def strokes_to_sequence(strokes: list[list[tuple[float, float]]], seq_len: int = SEQ_LEN) -> np.ndarray:
    raw: list[tuple[float, float, float]] = []
    for si, stroke in enumerate(strokes):
        for i, (x, y) in enumerate(stroke):
            pen_up = 1.0 if (i == len(stroke) - 1 and si < len(strokes) - 1) else 0.0
            raw.append((x, y, pen_up))
    if len(raw) < 2:
        return np.zeros((seq_len, FEAT_DIM), dtype=np.float32)
    xs = np.array([p[0] for p in raw], dtype=np.float64)
    ys = np.array([p[1] for p in raw], dtype=np.float64)
    pu = np.array([p[2] for p in raw], dtype=np.float64)
    sx = max(xs.max() - xs.min(), 1e-6)
    sy = max(ys.max() - ys.min(), 1e-6)
    xs = (xs - xs.min()) / sx
    ys = (ys - ys.min()) / sy
    diffs = np.sqrt(np.diff(xs, prepend=xs[0]) ** 2 + np.diff(ys, prepend=ys[0]) ** 2)
    cum = np.cumsum(diffs)
    if cum[-1] < 1e-9:
        cum = np.linspace(0, 1, len(cum))
    else:
        cum = cum / cum[-1]
    t_new = np.linspace(0, 1, seq_len)
    xs_r = np.interp(t_new, cum, xs)
    ys_r = np.interp(t_new, cum, ys)
    pu_r = np.interp(t_new, cum, pu)
    dx = np.diff(xs_r, prepend=xs_r[0])
    dy = np.diff(ys_r, prepend=ys_r[0])
    return np.stack([dx, dy, pu_r], axis=1).astype(np.float32)


def paths_json_to_strokes(paths_json: str | list | None) -> list[list[tuple[float, float]]]:
    if paths_json is None:
        return []
    if isinstance(paths_json, str):
        if not paths_json.strip():
            return []
        paths = json.loads(paths_json)
    else:
        paths = paths_json
    strokes: list[list[tuple[float, float]]] = []
    for path in paths or []:
        if not isinstance(path, dict) or not path.get("drawMode", True):
            continue
        pts = []
        for p in path.get("paths") or []:
            if isinstance(p, dict) and "x" in p and "y" in p:
                pts.append((float(p["x"]), float(p["y"])))
        if pts:
            strokes.append(pts)
    return strokes


def strokes_from_metrics_band(
    stroke_metrics: dict[str, Any] | None,
    band_bbox: dict[str, float] | None,
) -> list[list[tuple[float, float]]]:
    """Approximate strokes as bbox corners when full paths unavailable — weak; prefer paths_json."""
    if not stroke_metrics or not band_bbox:
        return []
    y0 = float(band_bbox.get("y", 0))
    y1 = y0 + float(band_bbox.get("h", 0))
    x0 = float(band_bbox.get("x", 0))
    x1 = x0 + float(band_bbox.get("w", 0)) if band_bbox.get("w") else 1e9
    strokes = []
    for s in stroke_metrics.get("strokes") or []:
        if not isinstance(s, dict) or s.get("tool") != "pen":
            continue
        bbox = s.get("bbox") or {}
        try:
            x, y, w, h = float(bbox["x"]), float(bbox["y"]), float(bbox["w"]), float(bbox["h"])
        except (KeyError, TypeError, ValueError):
            continue
        cy = y + h / 2
        if cy < y0 or cy > y1 or x + w < x0 or x > x1:
            continue
        # Diagonal + opposite as a crude stroke stand-in.
        strokes.append([(x, y), (x + w, y + h)])
    return strokes


def _featurize(X: np.ndarray, proj: np.ndarray | None = None) -> tuple[np.ndarray, np.ndarray]:
    n, t, f = X.shape
    dx, dy, pu = X[:, :, 0], X[:, :, 1], X[:, :, 2]
    stats = np.stack(
        [
            dx.mean(1),
            dy.mean(1),
            dx.std(1),
            dy.std(1),
            np.abs(dx).sum(1),
            np.abs(dy).sum(1),
            pu.mean(1),
            X[:, -1, 0] - X[:, 0, 0],
            X[:, -1, 1] - X[:, 0, 1],
        ],
        axis=1,
    ).astype(np.float32)
    flat = X.reshape(n, t * f)
    if proj is None:
        rng = np.random.default_rng(SEED)
        proj = rng.normal(0, 1 / math.sqrt(t * f), size=(t * f, HIDDEN - stats.shape[1])).astype(np.float32)
    return np.concatenate([stats, flat @ proj], axis=1), proj


def _fit_and_save(
    path: Path,
    samples: list[tuple[str, list[list[tuple[float, float]]]]],
) -> dict[str, Any]:
    if not samples:
        raise ValueError("no training samples")

    path.parent.mkdir(parents=True, exist_ok=True)
    labels = sorted({lbl for lbl, _ in samples})
    label_to_i = {lbl: i for i, lbl in enumerate(labels)}
    X = np.stack([strokes_to_sequence(st) for _, st in samples])
    y = np.array([label_to_i[lbl] for lbl, _ in samples], dtype=np.int64)
    Z, proj = _featurize(X)
    n_classes = len(labels)
    W = np.zeros((Z.shape[1], n_classes), dtype=np.float32)
    b = np.zeros(n_classes, dtype=np.float32)
    counts = np.bincount(y, minlength=n_classes).astype(np.float32)
    weights = counts.sum() / np.maximum(counts, 1.0)
    sample_w = weights[y]
    lr = 0.5
    for _ in range(200):
        logits = Z @ W + b
        logits -= logits.max(axis=1, keepdims=True)
        exp = np.exp(logits)
        probs = exp / np.maximum(exp.sum(axis=1, keepdims=True), 1e-9)
        y_oh = np.zeros_like(probs)
        y_oh[np.arange(len(y)), y] = 1.0
        grad = ((probs - y_oh).T * sample_w).T / sample_w.sum()
        W -= lr * (Z.T @ grad)
        b -= lr * grad.sum(axis=0)
        lr *= 0.995
    rng = np.random.default_rng(SEED)
    idx = rng.permutation(len(y))
    te = idx[int(0.8 * len(y)) :]
    Zte, _ = _featurize(X[te], proj)
    acc = float(((Zte @ W + b).argmax(1) == y[te]).mean()) if len(te) else 0.0
    np.savez_compressed(
        path,
        proj=proj,
        W=W,
        b=b,
        labels=np.array(labels, dtype=object),
        accuracy=np.array([acc]),
    )
    _load_model.cache_clear()
    return {
        "path": str(path),
        "accuracy": round(acc, 4),
        "classes": labels,
        "total_samples": len(samples),
    }


def train_and_save(
    path: Path | None = None,
    n_per_class: int = 40,
    *,
    extra_samples: list[tuple[str, list[list[tuple[float, float]]]]] | None = None,
    include_synthetic: bool = True,
    synth_per_class: int | None = None,
) -> dict[str, Any]:
    """Train softmax classifier; default augments with synthetic doodles."""
    path = path or MODEL_PATH
    samples: list[tuple[str, list[list[tuple[float, float]]]]] = []
    if include_synthetic:
        n = synth_per_class if synth_per_class is not None else n_per_class
        if n > 0:
            samples.extend(_synth_glyphs(n))
    if extra_samples:
        samples.extend(extra_samples)
    result = _fit_and_save(path, samples)
    result["real_samples"] = len(extra_samples or [])
    result["synthetic_augmented"] = include_synthetic and (synth_per_class or n_per_class) > 0
    return result


def train_from_handwriting_dataset(
    *,
    min_real_samples: int = 3,
    include_synthetic: bool = True,
    synth_per_class: int = 15,
    user_id: int | None = None,
    path: Path | None = None,
    rows: list[dict] | None = None,
) -> dict[str, Any]:
    """
    Retrain stroke-symbol model from DSC_handwriting_dataset paths_json + labels.

    Blends confirmed real ink with synthetic augments for classes that need coverage.
    """
    real, skip = collect_dataset_glyph_samples(rows=rows, user_id=user_id)
    if len(real) < min_real_samples:
        return {
            "status": "insufficient_samples",
            "message": f"Need at least {min_real_samples} real glyph samples with paths_json; have {len(real)}.",
            "real_samples": len(real),
            "skip_reasons": skip,
            "min_real_samples": min_real_samples,
        }

    by_label: dict[str, int] = {}
    for lbl, _ in real:
        by_label[lbl] = by_label.get(lbl, 0) + 1

    info = train_and_save(
        path=path,
        n_per_class=0,
        extra_samples=real,
        include_synthetic=include_synthetic,
        synth_per_class=synth_per_class,
    )
    return {
        "status": "trained",
        "message": f"Retrained on {len(real)} real samples (+ synthetic aug).",
        "real_samples": len(real),
        "samples_by_label": by_label,
        "skip_reasons": skip,
        **info,
    }


@lru_cache(maxsize=1)
def _load_model() -> tuple[np.ndarray, np.ndarray, np.ndarray, list[str]] | None:
    path = MODEL_PATH
    if not path.exists():
        try:
            train_and_save(path, n_per_class=40, include_synthetic=True)
        except Exception:
            return None
    try:
        data = np.load(path, allow_pickle=True)
        labels = [str(x) for x in data["labels"].tolist()]
        return data["proj"], data["W"], data["b"], labels
    except Exception:
        return None


def predict_symbol(
    strokes: list[list[tuple[float, float]]],
    *,
    min_confidence: float = 0.55,
) -> tuple[str, float] | None:
    """Return (label, confidence) or None if model unavailable / low confidence."""
    if not strokes:
        return None
    model = _load_model()
    if model is None:
        return None
    proj, W, b, labels = model
    X = strokes_to_sequence(strokes)[None, ...]
    Z, _ = _featurize(X, proj)
    logits = Z @ W + b
    logits -= logits.max(axis=1, keepdims=True)
    exp = np.exp(logits)
    probs = exp / np.maximum(exp.sum(axis=1, keepdims=True), 1e-9)
    i = int(probs.argmax())
    conf = float(probs[0, i])
    if conf < min_confidence:
        return None
    return labels[i], conf


def _norm_glyph(s: str) -> str:
    return (s or "").replace(" ", "").replace(r"\left", "").replace(r"\right", "").lower()


def maybe_disambiguate_latex(
    latex: str,
    *,
    confidence: float,
    paths_json: str | None = None,
    stroke_metrics: dict | None = None,
    band_bbox: dict | None = None,
    conf_threshold: float = 0.5,
    teacher_latex: str = "",
) -> tuple[str, float, str, bool]:
    """
    Ensemble vote: TexTeller + stroke_symbol (+ optional NIM teacher agree).

    Returns (latex, confidence, source, needs_review).
    """
    return _ensemble_vote(
        latex,
        confidence=confidence,
        paths_json=paths_json,
        stroke_metrics=stroke_metrics,
        band_bbox=band_bbox,
        conf_threshold=conf_threshold,
        teacher_latex=teacher_latex,
    )


def ensemble_needs_review(
    latex: str,
    *,
    confidence: float,
    paths_json: str | None = None,
    stroke_metrics: dict | None = None,
    band_bbox: dict | None = None,
    teacher_latex: str = "",
) -> bool:
    _l, _c, _s, needs = _ensemble_vote(
        latex,
        confidence=confidence,
        paths_json=paths_json,
        stroke_metrics=stroke_metrics,
        band_bbox=band_bbox,
        teacher_latex=teacher_latex,
    )
    return needs


def _ensemble_vote(
    latex: str,
    *,
    confidence: float,
    paths_json: str | None = None,
    stroke_metrics: dict | None = None,
    band_bbox: dict | None = None,
    conf_threshold: float = 0.5,
    teacher_latex: str = "",
) -> tuple[str, float, str, bool]:
    teacher = (teacher_latex or "").strip()
    ocr = (latex or "").strip()

    # NIM teacher auto-confirm when agree + high confidence
    if teacher and ocr and _norm_glyph(teacher) == _norm_glyph(ocr) and confidence >= 0.55:
        return ocr, min(1.0, confidence + 0.2), "nim_agree", False

    if confidence >= conf_threshold and ocr:
        if not teacher or _norm_glyph(teacher) == _norm_glyph(ocr):
            return ocr, confidence, "ocr", False
        return ocr, confidence * 0.85, "ocr", True

    strokes = paths_json_to_strokes(paths_json)
    if not strokes:
        strokes = strokes_from_metrics_band(stroke_metrics, band_bbox)
    if ocr and len(ocr.replace(" ", "")) > 4:
        return ocr, confidence, "ocr", bool(teacher and _norm_glyph(teacher) != _norm_glyph(ocr))

    pred = predict_symbol(strokes)
    if not pred:
        return ocr, confidence, "ocr", bool(teacher and teacher != ocr)

    label, stroke_conf = pred
    if ocr and _norm_glyph(label) == _norm_glyph(ocr):
        return ocr, min(1.0, max(confidence, stroke_conf) + 0.12), "ensemble_agree", False
    if stroke_conf > confidence and stroke_conf >= 0.55:
        disagree = bool(ocr and _norm_glyph(label) != _norm_glyph(ocr))
        return label, stroke_conf, "stroke_symbol", disagree
    if ocr and label and _norm_glyph(label) != _norm_glyph(ocr) and stroke_conf > 0.6 and confidence > 0.5:
        return ocr, confidence * 0.75, "ensemble_disagree", True
    return ocr or label, max(confidence, stroke_conf), "stroke_symbol" if not ocr else "ocr", False
