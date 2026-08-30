"""Bulk import MathWriting InkML excerpts into DSC_handwriting_dataset.csv."""

from __future__ import annotations

import hashlib
import json
import tarfile
import urllib.request
import uuid
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from datetime import UTC, datetime
from io import BytesIO
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image, ImageDraw

from backend.math.training_log import TRAINING_DIR, append_sample, _relative_data_path
from backend.paths import ROOT

EXCERPT_URL = "https://storage.googleapis.com/mathwriting_data/mathwriting-2024-excerpt.tgz"
DEFAULT_CACHE = ROOT / "data" / "math" / "mathwriting_cache"
CANVAS_W, CANVAS_H = 400, 120


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1] if "}" in tag else tag


def parse_inkml(path: Path) -> tuple[str, list[list[tuple[float, float]]]]:
    tree = ET.parse(path)
    root = tree.getroot()
    label = ""
    for ann in root.iter():
        if _local(ann.tag) != "annotation":
            continue
        t = (ann.attrib.get("type") or "").lower()
        text = (ann.text or "").strip()
        if not text:
            continue
        if t in ("label", "normalizedlabel") and not label:
            label = text
    strokes: list[list[tuple[float, float]]] = []
    for tr in root.iter():
        if _local(tr.tag) != "trace":
            continue
        raw = (tr.text or "").strip()
        if not raw:
            continue
        pts: list[tuple[float, float]] = []
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


def _normalize_strokes(
    strokes: list[list[tuple[float, float]]],
    *,
    width: int = CANVAS_W,
    height: int = CANVAS_H,
    margin: float = 0.08,
) -> list[list[tuple[float, float]]]:
    if not strokes:
        return []
    xs = [p[0] for s in strokes for p in s]
    ys = [p[1] for s in strokes for p in s]
    minx, maxx = min(xs), max(xs)
    miny, maxy = min(ys), max(ys)
    sx = max(maxx - minx, 1e-6)
    sy = max(maxy - miny, 1e-6)
    pad_x = width * margin
    pad_y = height * margin
    inner_w = width - 2 * pad_x
    inner_h = height - 2 * pad_y
    out: list[list[tuple[float, float]]] = []
    for stroke in strokes:
        row: list[tuple[float, float]] = []
        for x, y in stroke:
            nx = pad_x + (x - minx) / sx * inner_w
            ny = pad_y + (y - miny) / sy * inner_h
            row.append((nx, ny))
        if row:
            out.append(row)
    return out


def strokes_to_paths_json(strokes: list[list[tuple[float, float]]]) -> str:
    paths: list[dict[str, Any]] = []
    for stroke in strokes:
        paths.append(
            {
                "paths": [{"x": x, "y": y} for x, y in stroke],
                "strokeWidth": 3,
                "strokeColor": "#000000",
                "drawMode": True,
            }
        )
    return json.dumps(paths)


def rasterize_strokes(strokes: list[list[tuple[float, float]]]) -> bytes:
    img = Image.new("RGB", (CANVAS_W, CANVAS_H), "white")
    draw = ImageDraw.Draw(img)
    for stroke in strokes:
        if len(stroke) >= 2:
            draw.line(stroke, fill="black", width=3)
        elif len(stroke) == 1:
            x, y = stroke[0]
            draw.ellipse((x - 2, y - 2, x + 2, y + 2), fill="black")
    buf = BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def download_excerpt(cache_dir: Path | None = None) -> Path:
    cache = cache_dir or DEFAULT_CACHE
    cache.mkdir(parents=True, exist_ok=True)
    tgz = cache / "mathwriting-2024-excerpt.tgz"
    if not tgz.exists():
        urllib.request.urlretrieve(EXCERPT_URL, tgz)
    for p in cache.iterdir():
        if p.is_dir() and (list(p.rglob("*.inkml")) or (p / "symbols").is_dir()):
            return p
    with tarfile.open(tgz, "r:gz") as tar:
        tar.extractall(cache)
    for p in cache.iterdir():
        if p.is_dir():
            return p
    return cache


def iter_inkml_files(data_root: Path, *, max_files: int = 500) -> list[Path]:
    symbols_dir = data_root / "symbols"
    if symbols_dir.is_dir():
        files = sorted(symbols_dir.rglob("*.inkml"))
    else:
        files = sorted(data_root.rglob("*.inkml"))
    return files[:max_files]


@dataclass
class ImportResult:
    imported: int = 0
    skipped: int = 0
    skip_reasons: dict[str, int] = field(default_factory=dict)
    sample_ids: list[str] = field(default_factory=list)
    source: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "imported": self.imported,
            "skipped": self.skipped,
            "skip_reasons": self.skip_reasons,
            "sample_ids": self.sample_ids,
            "source": self.source,
        }


def _skip(reasons: dict[str, int], reason: str) -> None:
    reasons[reason] = reasons.get(reason, 0) + 1


def _dedupe_key(prompt_id: str, norm_label: str, paths_json: str) -> str:
    """
    Rebuild ``training_log._sample_dedupe_key`` for a row we have not written yet.

    Must stay byte-identical to that function's output, otherwise the key can never
    match anything in the CSV and cross-run duplicate detection silently does nothing.
    The ink hash is what keeps two different writers of the same symbol distinct.
    """
    stroke_hint = hashlib.sha1(paths_json.encode("utf-8")[:4096]).hexdigest()[:12]
    return f"{prompt_id}|{norm_label}|{stroke_hint}"


def import_mathwriting_samples(
    *,
    user_id: int,
    data_dir: Path | None = None,
    max_samples: int = 200,
    skip_duplicates: bool = True,
    download_if_missing: bool = True,
) -> ImportResult:
    """Import MathWriting InkML files as training CSV rows with PNG + paths_json."""
    from backend.math.training_log import find_duplicate_keys, _normalize_latex

    root = data_dir
    if root is None or not root.exists():
        if download_if_missing:
            root = download_excerpt()
        else:
            return ImportResult(skipped=1, skip_reasons={"no_data_dir": 1})

    result = ImportResult(source=str(root))
    existing_keys = find_duplicate_keys(user_id) if skip_duplicates else set()
    seen: set[str] = set()

    for inkml_path in iter_inkml_files(root, max_files=max_samples * 3):
        if result.imported >= max_samples:
            break
        try:
            label, raw_strokes = parse_inkml(inkml_path)
        except ET.ParseError:
            _skip(result.skip_reasons, "parse_error")
            result.skipped += 1
            continue
        if not label or not raw_strokes or len(label) > 24:
            _skip(result.skip_reasons, "empty_or_long_label")
            result.skipped += 1
            continue

        strokes = _normalize_strokes(raw_strokes)
        if not strokes:
            _skip(result.skip_reasons, "no_strokes")
            result.skipped += 1
            continue

        norm_label = _normalize_latex(label)
        prompt_id = f"mw-{inkml_path.stem[:32]}"
        paths_json = strokes_to_paths_json(strokes)
        key = _dedupe_key(prompt_id, norm_label, paths_json)
        if skip_duplicates and (key in existing_keys or key in seen):
            _skip(result.skip_reasons, "duplicate")
            result.skipped += 1
            continue

        sample_id = str(uuid.uuid4())
        png_bytes = rasterize_strokes(strokes)
        png_out = TRAINING_DIR / f"{sample_id}.png"
        png_out.write_bytes(png_bytes)
        paths_out = TRAINING_DIR / f"{sample_id}.paths.json"
        paths_out.write_text(paths_json, encoding="utf-8")

        append_sample(
            {
                "sample_id": sample_id,
                "timestamp": datetime.now(UTC).isoformat(),
                "tier": "mathwriting",
                "prompt_id": prompt_id,
                "prompt_text": label,
                "predicted_latex": "",
                "confirmed_latex": label,
                "teacher_latex": "",
                "agree": "imported",
                "png_path": _relative_data_path(png_out),
                "user_id": user_id,
                "action": "import",
                "paths_json_path": _relative_data_path(paths_out),
                "target_latex": label,
                "match_predicted": "",
            }
        )
        result.imported += 1
        result.sample_ids.append(sample_id)
        seen.add(key)

    return result
