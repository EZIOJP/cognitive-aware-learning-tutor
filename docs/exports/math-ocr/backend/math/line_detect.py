"""
Multi-line formula band detection for math OCR.

Primary (canvas): cluster pen-stroke bboxes by Y-overlap/gap.
Fallback (image-only): horizontal ink projection profile (Phase 0 validated).
Fraction guard merges bands that are too close relative to median band height.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import cv2
import numpy as np
from PIL import Image


@dataclass(frozen=True)
class LineBand:
    """Axis-aligned band covering one equation / step line."""

    y0: int
    y1: int
    x0: int = 0
    x1: int = 0
    stroke_indices: tuple[int, ...] = ()
    source: str = "unknown"

    @property
    def height(self) -> int:
        return max(0, self.y1 - self.y0)

    @property
    def width(self) -> int:
        return max(0, self.x1 - self.x0)

    def as_bbox(self) -> dict[str, int]:
        return {"x": self.x0, "y": self.y0, "w": self.width, "h": self.height}

    def padded(
        self,
        *,
        pad: int,
        img_w: int,
        img_h: int,
    ) -> LineBand:
        return LineBand(
            y0=max(0, self.y0 - pad),
            y1=min(img_h, self.y1 + pad),
            x0=max(0, self.x0 - pad),
            x1=min(img_w, self.x1 + pad) if self.x1 else img_w,
            stroke_indices=self.stroke_indices,
            source=self.source,
        )


def _pen_stroke_boxes(stroke_metrics: dict[str, Any] | None) -> list[tuple[int, float, float, float, float]]:
    """Return (stroke_index, x, y, w, h) for pen strokes with valid bboxes."""
    if not stroke_metrics or not isinstance(stroke_metrics, dict):
        return []
    strokes = stroke_metrics.get("strokes") or []
    out: list[tuple[int, float, float, float, float]] = []
    for s in strokes:
        if not isinstance(s, dict) or s.get("tool") != "pen":
            continue
        bbox = s.get("bbox") or {}
        try:
            idx = int(s.get("strokeIndex", len(out)))
            x = float(bbox["x"])
            y = float(bbox["y"])
            w = float(bbox["w"])
            h = float(bbox["h"])
        except (KeyError, TypeError, ValueError):
            continue
        if w <= 0 and h <= 0:
            continue
        # Dot strokes: give a tiny height so they still participate.
        if h <= 0:
            h = 1.0
        if w <= 0:
            w = 1.0
        out.append((idx, x, y, w, h))
    return out


def group_lines_from_strokes(
    stroke_metrics: dict[str, Any] | None,
    *,
    gap_ratio: float = 0.55,
    min_gap_px: float = 8.0,
) -> list[LineBand]:
    """
    Cluster pen-stroke bboxes into horizontal line bands.

    Two strokes belong to the same line when their Y intervals overlap, or the
    gap between them is smaller than max(min_gap_px, gap_ratio * median_height).
    """
    boxes = _pen_stroke_boxes(stroke_metrics)
    if not boxes:
        return []

    heights = [h for *_rest, h in boxes]
    median_h = float(np.median(heights)) if heights else 12.0
    merge_gap = max(min_gap_px, gap_ratio * median_h)

    # Sort by top Y then left X.
    boxes_sorted = sorted(boxes, key=lambda b: (b[2], b[1]))
    clusters: list[dict[str, Any]] = []

    for idx, x, y, w, h in boxes_sorted:
        y1 = y + h
        x1 = x + w
        placed = False
        for cl in clusters:
            # Gap between intervals (0 if overlap).
            gap = max(0.0, y - cl["y1"], cl["y0"] - y1)
            if gap <= merge_gap:
                cl["y0"] = min(cl["y0"], y)
                cl["y1"] = max(cl["y1"], y1)
                cl["x0"] = min(cl["x0"], x)
                cl["x1"] = max(cl["x1"], x1)
                cl["indices"].append(idx)
                placed = True
                break
        if not placed:
            clusters.append(
                {
                    "y0": y,
                    "y1": y1,
                    "x0": x,
                    "x1": x1,
                    "indices": [idx],
                }
            )

    # Sort clusters top-to-bottom and apply fraction guard.
    clusters.sort(key=lambda c: c["y0"])
    bands = [
        LineBand(
            y0=int(round(c["y0"])),
            y1=int(round(c["y1"])),
            x0=int(round(c["x0"])),
            x1=int(round(c["x1"])),
            stroke_indices=tuple(sorted(c["indices"])),
            source="stroke_bbox",
        )
        for c in clusters
    ]
    return apply_fraction_guard(bands)


def split_lines_projection(
    img: Image.Image,
    *,
    min_gap_rows: int = 8,
    pad: int = 0,
) -> list[LineBand]:
    """
    Horizontal projection profile: binarize, sum ink per row, split on empty gaps.
    Phase 0 validated on synthetic multi-line samples.
    """
    gray = np.array(img.convert("L"))
    _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    row_ink = binary.sum(axis=1)
    has_ink = row_ink > 0

    raw: list[tuple[int, int]] = []
    start: int | None = None
    gap = 0
    for y, ink in enumerate(has_ink):
        if ink:
            if start is None:
                start = y
            gap = 0
        elif start is not None:
            gap += 1
            if gap >= min_gap_rows:
                raw.append((start, y - gap + 1))
                start = None
                gap = 0
    if start is not None:
        raw.append((start, len(has_ink)))

    h, w = gray.shape
    # Compute x extent per band from ink columns.
    bands: list[LineBand] = []
    for y0, y1 in raw:
        strip = binary[y0:y1, :]
        cols = np.where(strip.sum(axis=0) > 0)[0]
        if len(cols) == 0:
            x0, x1 = 0, w
        else:
            x0, x1 = int(cols[0]), int(cols[-1]) + 1
        bands.append(
            LineBand(
                y0=max(0, y0 - pad),
                y1=min(h, y1 + pad),
                x0=max(0, x0 - pad),
                x1=min(w, x1 + pad),
                source="projection",
            )
        )
    return apply_fraction_guard(bands)


def apply_fraction_guard(
    bands: list[LineBand],
    *,
    merge_ratio: float = 0.35,
) -> list[LineBand]:
    """
    Merge adjacent bands whose vertical gap is small relative to median height.

    Prevents splitting a fraction bar from its numerator/denominator when the
    initial clustering was slightly too aggressive.
    """
    if len(bands) <= 1:
        return list(bands)

    heights = [b.height for b in bands if b.height > 0]
    median_h = float(np.median(heights)) if heights else 12.0
    max_gap = max(4.0, merge_ratio * median_h)

    merged: list[LineBand] = [bands[0]]
    for b in bands[1:]:
        prev = merged[-1]
        gap = max(0, b.y0 - prev.y1)
        if gap <= max_gap:
            merged[-1] = LineBand(
                y0=min(prev.y0, b.y0),
                y1=max(prev.y1, b.y1),
                x0=min(prev.x0, b.x0) if (prev.x1 or b.x1) else 0,
                x1=max(prev.x1, b.x1),
                stroke_indices=tuple(sorted(set(prev.stroke_indices) | set(b.stroke_indices))),
                source=prev.source if prev.source == b.source else "merged",
            )
        else:
            merged.append(b)
    return merged


def detect_line_bands(
    img: Image.Image,
    stroke_metrics: dict[str, Any] | None = None,
    *,
    pad: int = 12,
    use_mfd_fallback: bool = True,
) -> list[LineBand]:
    """
    Prefer stroke-bbox clustering when metrics are present; else projection.
    If both yield fewer than 2 bands but the image has substantial multi-row ink,
    optionally try MFD ONNX as an upgrade path.
    """
    w, h = img.size
    bands = group_lines_from_strokes(stroke_metrics)
    if len(bands) < 1:
        bands = split_lines_projection(img)

    need_upgrade = len(bands) < 2 and use_mfd_fallback
    if need_upgrade:
        try:
            from backend.math.mfd_onnx import boxes_to_line_bands, detect_formula_boxes, mfd_available

            if mfd_available():
                mfd_boxes = detect_formula_boxes(img)
                if len(mfd_boxes) >= 2:
                    bands = boxes_to_line_bands(mfd_boxes)
        except Exception:
            pass

    if not bands:
        return []
    return [b.padded(pad=pad, img_w=w, img_h=h) for b in bands]
