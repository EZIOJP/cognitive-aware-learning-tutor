"""Learned structure verifier — small MLP on bbox features (Phase E)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from backend.paths import ROOT

MODEL_PATH = ROOT / "data" / "math" / "structure_mlp.npz"
FEAT_DIM = 12


@dataclass
class LearnedVerifyResult:
    confidence_boost: float
    matrix_detected: bool
    loaded: bool


def _bbox_features(boxes: list[dict[str, float]]) -> np.ndarray:
    if not boxes:
        return np.zeros(FEAT_DIM, dtype=np.float32)
    hs = [b["h"] for b in boxes]
    ws = [b["w"] for b in boxes]
    xs = [b["x"] for b in boxes]
    ys = [b["y"] for b in boxes]
    median_h = float(np.median(hs))
    median_w = float(np.median(ws))
    cols = len({round(x / max(median_w, 1.0)) for x in xs})
    rows = len({round(y / max(median_h, 1.0)) for y in ys})
    aspect = float(np.mean([w / max(h, 1.0) for w, h in zip(ws, hs, strict=True)]))
    spread_x = float(max(xs) - min(xs)) if xs else 0.0
    spread_y = float(max(ys) - min(ys)) if ys else 0.0
    bar_like = float(
        sum(1 for b in boxes if b["w"] / max(b["h"], 1.0) >= 3.0) / max(len(boxes), 1)
    )
    small = float(sum(1 for h in hs if h < 0.7 * median_h) / max(len(hs), 1))
    tall = float(sum(1 for h in hs if h > 1.4 * median_h) / max(len(hs), 1))
    return np.array(
        [
            len(boxes) / 20.0,
            median_h / 100.0,
            median_w / 100.0,
            aspect,
            spread_x / 500.0,
            spread_y / 200.0,
            cols / 6.0,
            rows / 4.0,
            bar_like,
            small,
            tall,
            1.0 if cols >= 3 and rows >= 2 else 0.0,
        ],
        dtype=np.float32,
    )


def _default_weights() -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    rng = np.random.default_rng(42)
    W1 = rng.normal(0, 0.15, size=(FEAT_DIM, 16)).astype(np.float32)
    b1 = np.zeros(16, dtype=np.float32)
    W2 = rng.normal(0, 0.15, size=(16, 1)).astype(np.float32)
    b2 = np.zeros(1, dtype=np.float32)
    return W1, b1, W2, b2


def _load_model() -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray] | None:
    if not MODEL_PATH.is_file():
        return None
    try:
        data = np.load(MODEL_PATH)
        return data["W1"], data["b1"], data["W2"], data["b2"]
    except Exception:
        return None


def save_default_model() -> Path:
    MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    W1, b1, W2, b2 = _default_weights()
    np.savez(MODEL_PATH, W1=W1, b1=b1, W2=W2, b2=b2)
    return MODEL_PATH


def train_from_labels(
    samples: list[tuple[list[dict[str, float]], float]],
) -> Path:
    """Fit MLP on (boxes, target_confidence) pairs; saves structure_mlp.npz."""
    if len(samples) < 3:
        return save_default_model()
    X = np.stack([_bbox_features(b) for b, _ in samples])
    y = np.array([t for _, t in samples], dtype=np.float32).reshape(-1, 1)
    W1, b1, W2, b2 = _default_weights()
    lr = 0.05
    for _ in range(300):
        z1 = np.maximum(0, X @ W1 + b1)
        pred = 1 / (1 + np.exp(-(z1 @ W2 + b2)))
        grad = (pred - y) / len(y)
        W2 -= lr * (z1.T @ grad)
        b2 -= lr * grad.sum(axis=0)
        dz1 = grad @ W2.T
        dz1[z1 <= 0] = 0
        W1 -= lr * (X.T @ dz1)
        b1 -= lr * dz1.sum(axis=0)
    MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    np.savez(MODEL_PATH, W1=W1, b1=b1, W2=W2, b2=b2)
    return MODEL_PATH


def predict_learned_confidence(boxes: list[dict[str, float]]) -> LearnedVerifyResult:
    feat = _bbox_features(boxes)
    matrix = bool(feat[11] >= 1.0)
    weights = _load_model()
    if weights is None:
        boost = 0.05 if matrix else 0.0
        return LearnedVerifyResult(confidence_boost=boost, matrix_detected=matrix, loaded=False)
    W1, b1, W2, b2 = weights
    z1 = np.maximum(0, feat @ W1 + b1)
    score = float(1 / (1 + np.exp(-float(z1 @ W2 + b2))))
    boost = (score - 0.5) * 0.2
    return LearnedVerifyResult(confidence_boost=boost, matrix_detected=matrix, loaded=True)


def detect_matrix_layout(boxes: list[dict[str, float]]) -> bool:
    """True when stroke bboxes form a grid (≥3 cols × ≥2 rows)."""
    if len(boxes) < 6:
        return False
    hs = [b["h"] for b in boxes]
    ws = [b["w"] for b in boxes]
    mh = float(np.median(hs)) or 1.0
    mw = float(np.median(ws)) or 1.0
    cols = len({round(b["x"] / mw) for b in boxes})
    rows = len({round(b["y"] / mh) for b in boxes})
    return cols >= 3 and rows >= 2
