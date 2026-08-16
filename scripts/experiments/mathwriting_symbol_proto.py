"""
Track B — MathWriting stroke-sequence symbol classifier prototype.

Downloads the official 1.5 MB MathWriting excerpt (CC BY-NC-SA 4.0), parses
InkML strokes, trains a tiny numpy softmax classifier on resampled
(dx, dy, pen_up) features, and reports held-out accuracy.

Also demos inference on CALT paths_json if present under data_logs/training.

Run:
  .venv\\Scripts\\python.exe scripts\\experiments\\mathwriting_symbol_proto.py

Optional:
  --data-dir PATH   use an already-extracted MathWriting root
  --skip-download   do not fetch excerpt
"""

from __future__ import annotations

import argparse
import json
import math
import random
import sys
import tarfile
import urllib.request
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).parent / "out"
DEFAULT_CACHE = OUT / "mathwriting_excerpt"
EXCERPT_URL = "https://storage.googleapis.com/mathwriting_data/mathwriting-2024-excerpt.tgz"
SEQ_LEN = 64
FEAT_DIM = 3  # dx, dy, pen_up
HIDDEN = 64
SEED = 42


def download_excerpt(cache_dir: Path) -> Path:
    cache_dir.mkdir(parents=True, exist_ok=True)
    tgz = cache_dir / "mathwriting-2024-excerpt.tgz"
    if not tgz.exists():
        print(f"Downloading {EXCERPT_URL} …")
        urllib.request.urlretrieve(EXCERPT_URL, tgz)
    # Find already-extracted root or extract.
    for child in cache_dir.iterdir():
        if child.is_dir() and (child / "symbols").is_dir() or list(child.glob("**/symbols")):
            # Prefer directory that contains symbols/
            pass
    extracted_roots = [p for p in cache_dir.iterdir() if p.is_dir()]
    for p in extracted_roots:
        if (p / "symbols").is_dir() or list(p.rglob("*.inkml")):
            return p
    print(f"Extracting {tgz} …")
    with tarfile.open(tgz, "r:gz") as tar:
        tar.extractall(cache_dir)
    for p in cache_dir.iterdir():
        if p.is_dir():
            return p
    return cache_dir


def _local(tag: str) -> str:
    if "}" in tag:
        return tag.rsplit("}", 1)[-1]
    return tag


def parse_inkml(path: Path) -> tuple[str, list[list[tuple[float, float]]]]:
    """Return (label, strokes) where each stroke is a list of (x, y)."""
    tree = ET.parse(path)
    root = tree.getroot()
    label = ""
    strokes: list[list[tuple[float, float]]] = []
    # Prefer <annotation type="label"> then normalizedLabel.
    for ann in root.iter():
        if _local(ann.tag) != "annotation":
            continue
        t = (ann.attrib.get("type") or "").lower()
        text = (ann.text or "").strip()
        if not text:
            continue
        if t == "label" and not label:
            label = text
        elif t == "normalizedlabel" and not label:
            label = text
    # Traces
    for tr in root.iter():
        if _local(tr.tag) != "trace":
            continue
        pts: list[tuple[float, float]] = []
        raw = (tr.text or "").strip()
        if not raw:
            continue
        for token in raw.replace(",", " ").split():
            # InkML often "x y" or "x y t" per point; points separated by commas.
            pass
        # Proper split: points are comma-separated, each "x y [t]"
        for point in raw.split(","):
            nums = point.strip().split()
            if len(nums) >= 2:
                try:
                    pts.append((float(nums[0]), float(nums[1])))
                except ValueError:
                    continue
        if pts:
            strokes.append(pts)
    return label, strokes


def load_symbol_samples(data_root: Path, max_per_class: int = 80) -> list[tuple[str, list[list[tuple[float, float]]]]]:
    """Load from symbols/ if present, else any short inkml under the tree."""
    samples: list[tuple[str, list]] = []
    symbols_dir = None
    for cand in [data_root / "symbols", *data_root.rglob("symbols")]:
        if cand.is_dir():
            symbols_dir = cand
            break

    inkmls: list[Path] = []
    if symbols_dir:
        inkmls = sorted(symbols_dir.glob("*.inkml")) + sorted(symbols_dir.glob("**/*.inkml"))
    if not inkmls:
        # Excerpt may only have a handful of train samples — take short ones.
        inkmls = sorted(data_root.rglob("*.inkml"))[:200]

    by_label: dict[str, int] = defaultdict(int)
    for p in inkmls:
        try:
            label, strokes = parse_inkml(p)
        except ET.ParseError:
            continue
        if not label or not strokes:
            continue
        # Normalize tiny labels
        label = label.strip()
        if len(label) > 12:
            continue  # skip full expressions for this isolated-symbol proto
        if by_label[label] >= max_per_class:
            continue
        by_label[label] += 1
        samples.append((label, strokes))
    return samples


def strokes_to_sequence(strokes: list[list[tuple[float, float]]], seq_len: int = SEQ_LEN) -> np.ndarray:
    """Resample ink to fixed-length (dx, dy, pen_up) features, normalized."""
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
    # Normalize to unit box
    minx, maxx = xs.min(), xs.max()
    miny, maxy = ys.min(), ys.max()
    sx = max(maxx - minx, 1e-6)
    sy = max(maxy - miny, 1e-6)
    xs = (xs - minx) / sx
    ys = (ys - miny) / sy

    # Uniform resample along arc length
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
    feats = np.stack([dx, dy, pu_r], axis=1).astype(np.float32)
    return feats


def paths_json_to_strokes(paths_json: str | list) -> list[list[tuple[float, float]]]:
    if isinstance(paths_json, str):
        paths = json.loads(paths_json)
    else:
        paths = paths_json
    strokes: list[list[tuple[float, float]]] = []
    for path in paths:
        if not isinstance(path, dict) or not path.get("drawMode", True):
            continue
        pts = []
        for p in path.get("paths") or []:
            if isinstance(p, dict) and "x" in p and "y" in p:
                pts.append((float(p["x"]), float(p["y"])))
        if pts:
            strokes.append(pts)
    return strokes


def synthesize_fallback(n_per_class: int = 40) -> list[tuple[str, list[list[tuple[float, float]]]]]:
    """If excerpt has too few symbols, synthesize simple digit / operator strokes."""
    rng = random.Random(SEED)
    samples = []
    glyphs = {
        "0": lambda: _ellipse(rng),
        "1": lambda: _vline(rng),
        "2": lambda: _two(rng),
        "3": lambda: _three(rng),
        "+": lambda: _plus(rng),
        "-": lambda: _hline(rng),
        "x": lambda: _xmark(rng),
        "=": lambda: _equals(rng),
    }
    for label, gen in glyphs.items():
        for _ in range(n_per_class):
            samples.append((label, gen()))
    return samples


def _jitter(pts, rng, s=0.04):
    return [(x + rng.uniform(-s, s), y + rng.uniform(-s, s)) for x, y in pts]


def _ellipse(rng):
    pts = [(0.5 + 0.35 * math.cos(t), 0.5 + 0.4 * math.sin(t)) for t in np.linspace(0, 2 * math.pi, 40)]
    return [_jitter(pts, rng)]


def _vline(rng):
    pts = [(0.5, y) for y in np.linspace(0.1, 0.9, 30)]
    return [_jitter(pts, rng)]


def _hline(rng):
    pts = [(x, 0.5) for x in np.linspace(0.15, 0.85, 25)]
    return [_jitter(pts, rng)]


def _plus(rng):
    return [_jitter([(x, 0.5) for x in np.linspace(0.2, 0.8, 20)], rng),
            _jitter([(0.5, y) for y in np.linspace(0.2, 0.8, 20)], rng)]


def _equals(rng):
    return [_jitter([(x, 0.35) for x in np.linspace(0.2, 0.8, 20)], rng),
            _jitter([(x, 0.65) for x in np.linspace(0.2, 0.8, 20)], rng)]


def _xmark(rng):
    return [_jitter([(t, t) for t in np.linspace(0.2, 0.8, 20)], rng),
            _jitter([(t, 1 - t) for t in np.linspace(0.2, 0.8, 20)], rng)]


def _two(rng):
    pts = [(0.25, 0.3), (0.5, 0.15), (0.75, 0.3), (0.7, 0.5), (0.3, 0.85), (0.8, 0.85)]
    dense = []
    for i in range(len(pts) - 1):
        for a in np.linspace(0, 1, 8):
            dense.append((pts[i][0] * (1 - a) + pts[i + 1][0] * a,
                          pts[i][1] * (1 - a) + pts[i + 1][1] * a))
    return [_jitter(dense, rng)]


def _three(rng):
    pts = [(0.3, 0.2), (0.7, 0.2), (0.55, 0.5), (0.7, 0.5), (0.7, 0.8), (0.3, 0.8)]
    dense = []
    for i in range(len(pts) - 1):
        for a in np.linspace(0, 1, 8):
            dense.append((pts[i][0] * (1 - a) + pts[i + 1][0] * a,
                          pts[i][1] * (1 - a) + pts[i + 1][1] * a))
    return [_jitter(dense, rng)]


def fit_predict(X_train, y_train, X_test, n_classes, epochs=200):
    n, t, f = X_train.shape
    # Feature: mean/std of dx,dy + final displacement + pen-up rate + random proj
    def hand(X, proj=None):
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
        flat = X.reshape(len(X), t * f)
        if proj is None:
            rng = np.random.default_rng(SEED)
            proj = rng.normal(0, 1 / math.sqrt(t * f), size=(t * f, HIDDEN - stats.shape[1])).astype(np.float32)
        return np.concatenate([stats, flat @ proj], axis=1), proj

    Z, proj = hand(X_train)
    W = np.zeros((Z.shape[1], n_classes), dtype=np.float32)
    b = np.zeros(n_classes, dtype=np.float32)
    counts = np.bincount(y_train, minlength=n_classes).astype(np.float32)
    weights = counts.sum() / np.maximum(counts, 1.0)
    sample_w = weights[y_train]
    lr = 0.5
    for _ in range(epochs):
        logits = Z @ W + b
        logits -= logits.max(axis=1, keepdims=True)
        exp = np.exp(logits)
        probs = exp / np.maximum(exp.sum(axis=1, keepdims=True), 1e-9)
        y_oh = np.zeros_like(probs)
        y_oh[np.arange(n), y_train] = 1.0
        grad = ((probs - y_oh).T * sample_w).T / sample_w.sum()
        W -= lr * (Z.T @ grad)
        b -= lr * grad.sum(axis=0)
        lr *= 0.995
    Zt, _ = hand(X_test, proj=proj)
    preds = (Zt @ W + b).argmax(axis=1)
    return preds, (proj, W, b)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", type=Path, default=None)
    ap.add_argument("--skip-download", action="store_true")
    args = ap.parse_args()

    OUT.mkdir(parents=True, exist_ok=True)
    report: dict = {"source": None, "n_samples": 0, "classes": {}, "accuracy": None, "notes": []}

    data_root = args.data_dir
    if data_root is None:
        # Prefer already-extracted excerpt cache even with --skip-download.
        cached = DEFAULT_CACHE / "mathwriting-2024-excerpt"
        if cached.is_dir():
            data_root = cached
        elif not args.skip_download:
            try:
                data_root = download_excerpt(DEFAULT_CACHE)
                report["source"] = f"mathwriting-excerpt:{data_root}"
            except Exception as e:
                report["notes"].append(f"download_failed: {e}")
                data_root = None
        else:
            report["notes"].append("skip_download_and_no_cache")

    samples: list[tuple[str, list]] = []
    if data_root and Path(data_root).exists():
        samples = load_symbol_samples(Path(data_root))
        report["notes"].append(f"parsed_inkml={len(samples)}")
        report["source"] = f"mathwriting:{data_root}"

    if len(samples) < 30:
        report["notes"].append("few_real_symbols_using_synthetic_fallback")
        samples = synthesize_fallback(50)
        report["source"] = (report.get("source") or "none") + "+synthetic_strokes"
    else:
        # Excerpt often lacks a broad symbols/ set — always blend synthetic
        # digits/operators so the prototype demonstrates multi-class learning.
        syn = synthesize_fallback(30)
        samples = samples + syn
        report["notes"].append(f"augmented_with_synthetic={len(syn)}")
        report["source"] = (report.get("source") or "unknown") + "+synthetic_aug"

    # Keep classes with at least 5 samples
    counts = Counter(lbl for lbl, _ in samples)
    keep = {lbl for lbl, c in counts.items() if c >= 5}
    samples = [(lbl, st) for lbl, st in samples if lbl in keep]
    labels = sorted(keep)
    label_to_i = {lbl: i for i, lbl in enumerate(labels)}
    report["classes"] = {lbl: counts[lbl] for lbl in labels}
    report["n_samples"] = len(samples)

    X = np.stack([strokes_to_sequence(st) for _, st in samples])
    y = np.array([label_to_i[lbl] for lbl, _ in samples], dtype=np.int64)

    rng = np.random.default_rng(SEED)
    idx = rng.permutation(len(y))
    split = max(1, int(0.8 * len(y)))
    train_idx, test_idx = idx[:split], idx[split:]
    if len(test_idx) == 0:
        test_idx = train_idx[: max(1, len(train_idx) // 5)]

    preds, model = fit_predict(X[train_idx], y[train_idx], X[test_idx], len(labels))
    acc = float((preds == y[test_idx]).mean()) if len(test_idx) else 0.0
    report["accuracy"] = round(acc, 4)
    report["n_train"] = int(len(train_idx))
    report["n_test"] = int(len(test_idx))
    report["model"] = "random_proj_softmax_numpy"
    report["seq_len"] = SEQ_LEN

    # Demo on CALT paths if present
    calt_demos = []
    proj, W, b = model
    t, f = SEQ_LEN, FEAT_DIM

    def predict_one(strokes):
        feat = strokes_to_sequence(strokes)[None, ...]
        dx, dy, pu = feat[:, :, 0], feat[:, :, 1], feat[:, :, 2]
        stats = np.stack(
            [
                dx.mean(1),
                dy.mean(1),
                dx.std(1),
                dy.std(1),
                np.abs(dx).sum(1),
                np.abs(dy).sum(1),
                pu.mean(1),
                feat[:, -1, 0] - feat[:, 0, 0],
                feat[:, -1, 1] - feat[:, 0, 1],
            ],
            axis=1,
        ).astype(np.float32)
        z = np.concatenate([stats, feat.reshape(1, -1) @ proj], axis=1)
        return int((z @ W + b).argmax())

    for d in [ROOT / "data_logs" / "training", ROOT / "data" / "logs" / "training"]:
        if not d.is_dir():
            continue
        for p in sorted(d.glob("*.paths.json"))[:5]:
            try:
                strokes = paths_json_to_strokes(p.read_text(encoding="utf-8"))
                if not strokes:
                    continue
                pred_i = predict_one(strokes)
                calt_demos.append({"path": str(p.name), "pred": labels[pred_i]})
            except Exception as e:
                calt_demos.append({"path": str(p.name), "error": str(e)})
    report["calt_paths_demo"] = calt_demos
    report["notes"].append(
        "Prototype only — use as low-confidence disambiguator later; not wired into OCR v1."
    )
    report["license"] = "MathWriting CC BY-NC-SA 4.0 (when using Google data)"

    out_path = OUT / "mathwriting_proto_results.json"
    out_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    # Also write a short markdown report
    md = OUT / "mathwriting_proto_report.md"
    md.write_text(
        "\n".join(
            [
                "# Track B — MathWriting symbol classifier prototype",
                "",
                f"- Source: `{report.get('source')}`",
                f"- Samples: **{report['n_samples']}** across **{len(labels)}** classes",
                f"- Held-out accuracy: **{report['accuracy']}** "
                f"(train={report['n_train']}, test={report['n_test']})",
                f"- Model: numpy random-projection + softmax (no torch; throwaway-env ready)",
                f"- CALT paths demos: {len(calt_demos)}",
                "",
                "## Classes",
                "",
                "```json",
                json.dumps(report["classes"], indent=2),
                "```",
                "",
                "## Notes",
                "",
                *[f"- {n}" for n in report["notes"]],
                "",
                "Full JSON: `scripts/experiments/out/mathwriting_proto_results.json`",
                "",
                "Next: download full MathWriting (`symbols/` ~6423 inks) and swap GRU/Transformer;",
                "export ONNX for optional disambiguation in low-confidence OCR regions.",
            ]
        ),
        encoding="utf-8",
    )
    print(json.dumps(report, indent=2))
    print(f"Wrote {out_path}")
    print(f"Wrote {md}")


if __name__ == "__main__":
    main()
