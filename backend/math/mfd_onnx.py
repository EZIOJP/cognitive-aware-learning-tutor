"""
Pix2Text MFD 1.5 ONNX — formula region detection (YOLOv8-style).

Model: breezedeus/pix2text-mfd-1.5 (pix2text-mfd-1.5.onnx, ~80 MB).
Output layout from Phase 0 probe: [1, 6, N] = cx, cy, w, h, cls0, cls1.

Used as an upgrade path when stroke-bbox / projection heuristics fail to
split multi-line ink. Optional — never required for OCR to work.
"""

from __future__ import annotations

import logging
from functools import lru_cache
from typing import Any

import cv2
import numpy as np
from PIL import Image

logger = logging.getLogger(__name__)

MFD_REPO = "breezedeus/pix2text-mfd-1.5"
MFD_FILE = "pix2text-mfd-1.5.onnx"
MFD_INPUT_SIZE = 768
DEFAULT_CONF = 0.25
DEFAULT_IOU = 0.45


def mfd_available() -> bool:
    try:
        import onnxruntime  # noqa: F401
        from huggingface_hub import hf_hub_download  # noqa: F401

        return True
    except ImportError:
        return False


@lru_cache(maxsize=1)
def _session():
    if not mfd_available():
        return None
    try:
        from huggingface_hub import hf_hub_download
        import onnxruntime as ort

        path = hf_hub_download(MFD_REPO, MFD_FILE)
        return ort.InferenceSession(path, providers=["CPUExecutionProvider"])
    except Exception as e:
        logger.warning("MFD ONNX load failed: %s", e)
        return None


def _letterbox(
    img_bgr: np.ndarray,
    size: int = MFD_INPUT_SIZE,
) -> tuple[np.ndarray, float, tuple[int, int]]:
    """Resize with padding; return (blob_rgb_nchw-ready HxWx3 float0-1), scale, (pad_x, pad_y)."""
    h, w = img_bgr.shape[:2]
    scale = min(size / max(h, 1), size / max(w, 1))
    nh, nw = int(round(h * scale)), int(round(w * scale))
    resized = cv2.resize(img_bgr, (nw, nh), interpolation=cv2.INTER_LINEAR)
    canvas = np.full((size, size, 3), 114, dtype=np.uint8)
    pad_x = (size - nw) // 2
    pad_y = (size - nh) // 2
    canvas[pad_y : pad_y + nh, pad_x : pad_x + nw] = resized
    rgb = cv2.cvtColor(canvas, cv2.COLOR_BGR2RGB).astype(np.float32) / 255.0
    return rgb, scale, (pad_x, pad_y)


def _xywh_to_xyxy(cx: float, cy: float, w: float, h: float) -> tuple[float, float, float, float]:
    return cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2


def _nms(boxes: list[list[float]], scores: list[float], iou_thresh: float) -> list[int]:
    if not boxes:
        return []
    b = np.array(boxes, dtype=np.float32)
    s = np.array(scores, dtype=np.float32)
    x1, y1, x2, y2 = b[:, 0], b[:, 1], b[:, 2], b[:, 3]
    areas = np.maximum(0, x2 - x1) * np.maximum(0, y2 - y1)
    order = s.argsort()[::-1]
    keep: list[int] = []
    while order.size > 0:
        i = int(order[0])
        keep.append(i)
        if order.size == 1:
            break
        xx1 = np.maximum(x1[i], x1[order[1:]])
        yy1 = np.maximum(y1[i], y1[order[1:]])
        xx2 = np.minimum(x2[i], x2[order[1:]])
        yy2 = np.minimum(y2[i], y2[order[1:]])
        inter = np.maximum(0, xx2 - xx1) * np.maximum(0, yy2 - yy1)
        iou = inter / np.maximum(areas[i] + areas[order[1:]] - inter, 1e-6)
        order = order[1:][iou <= iou_thresh]
    return keep


def detect_formula_boxes(
    img: Image.Image,
    *,
    conf_thresh: float = DEFAULT_CONF,
    iou_thresh: float = DEFAULT_IOU,
) -> list[dict[str, Any]]:
    """
    Detect formula regions. Returns list of
    {x, y, w, h, score, class_id} in original image coordinates, top-to-bottom.
    Empty list if model unavailable or no detections.
    """
    sess = _session()
    if sess is None:
        return []

    rgb = np.array(img.convert("RGB"))
    bgr = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
    orig_h, orig_w = bgr.shape[:2]
    letter, scale, (pad_x, pad_y) = _letterbox(bgr)
    blob = letter.transpose(2, 0, 1)[None, ...]  # 1,3,H,W

    inp = sess.get_inputs()[0]
    try:
        out = sess.run(None, {inp.name: blob})[0]
    except Exception as e:
        logger.warning("MFD inference failed: %s", e)
        return []

    # Expect [1, 6, N] or [1, N, 6]
    arr = np.asarray(out)
    if arr.ndim != 3:
        return []
    if arr.shape[1] == 6:
        preds = arr[0].T  # N, 6
    elif arr.shape[2] == 6:
        preds = arr[0]
    else:
        # Try 4+nc generic
        if arr.shape[1] > arr.shape[2]:
            preds = arr[0].T
        else:
            preds = arr[0]

    boxes: list[list[float]] = []
    scores: list[float] = []
    classes: list[int] = []
    for row in preds:
        if row.shape[0] < 6:
            continue
        cx, cy, bw, bh = float(row[0]), float(row[1]), float(row[2]), float(row[3])
        cls_scores = row[4:]
        cls_id = int(np.argmax(cls_scores))
        score = float(cls_scores[cls_id])
        if score < conf_thresh:
            continue
        x0, y0, x1, y1 = _xywh_to_xyxy(cx, cy, bw, bh)
        # Undo letterbox
        x0 = (x0 - pad_x) / max(scale, 1e-6)
        y0 = (y0 - pad_y) / max(scale, 1e-6)
        x1 = (x1 - pad_x) / max(scale, 1e-6)
        y1 = (y1 - pad_y) / max(scale, 1e-6)
        x0 = float(np.clip(x0, 0, orig_w - 1))
        y0 = float(np.clip(y0, 0, orig_h - 1))
        x1 = float(np.clip(x1, 0, orig_w))
        y1 = float(np.clip(y1, 0, orig_h))
        if x1 - x0 < 2 or y1 - y0 < 2:
            continue
        boxes.append([x0, y0, x1, y1])
        scores.append(score)
        classes.append(cls_id)

    keep = _nms(boxes, scores, iou_thresh)
    results = []
    for i in keep:
        x0, y0, x1, y1 = boxes[i]
        results.append(
            {
                "x": int(round(x0)),
                "y": int(round(y0)),
                "w": int(round(x1 - x0)),
                "h": int(round(y1 - y0)),
                "score": round(scores[i], 4),
                "class_id": classes[i],
            }
        )
    results.sort(key=lambda r: (r["y"], r["x"]))
    return results


def boxes_to_line_bands(boxes: list[dict[str, Any]]):
    """Convert MFD boxes to LineBand objects (lazy import to avoid cycles)."""
    from backend.math.line_detect import LineBand

    return [
        LineBand(
            y0=b["y"],
            y1=b["y"] + b["h"],
            x0=b["x"],
            x1=b["x"] + b["w"],
            source="mfd",
        )
        for b in boxes
    ]
