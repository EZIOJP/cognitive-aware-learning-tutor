"""MyScript-inspired stroke order normalization for paths_json (Phase 3)."""

from __future__ import annotations

import json
from typing import Any


def _stroke_centroid(stroke: list[dict[str, float]]) -> tuple[float, float]:
    if not stroke:
        return 0.0, 0.0
    xs = [p["x"] for p in stroke if "x" in p and "y" in p]
    ys = [p["y"] for p in stroke if "x" in p and "y" in p]
    if not xs:
        return 0.0, 0.0
    return sum(xs) / len(xs), sum(ys) / len(ys)


def normalize_paths_json_stroke_order(paths_json: str | None) -> str | None:
    """
    Sort pen strokes top-to-bottom, then left-to-right (rough X-Y cut).
    Returns reordered paths JSON string.
    """
    if not (paths_json or "").strip():
        return paths_json
    try:
        paths = json.loads(paths_json)
    except (json.JSONDecodeError, TypeError):
        return paths_json
    if not isinstance(paths, list):
        return paths_json

    pen_paths: list[dict[str, Any]] = []
    other: list[dict[str, Any]] = []
    for path in paths:
        if not isinstance(path, dict):
            continue
        if path.get("drawMode", True):
            pen_paths.append(path)
        else:
            other.append(path)

    def sort_key(p: dict[str, Any]) -> tuple[float, float]:
        pts = p.get("paths") or []
        if not isinstance(pts, list):
            return (0.0, 0.0)
        stroke_pts = [{"x": float(pt["x"]), "y": float(pt["y"])} for pt in pts if isinstance(pt, dict) and "x" in pt and "y" in pt]
        cy, cx = _stroke_centroid(stroke_pts)
        return (cy, cx)

    pen_paths.sort(key=sort_key)
    merged = pen_paths + other
    return json.dumps(merged)
