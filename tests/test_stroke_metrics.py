"""Backend parsing of MathGridCanvas stroke metrics + kinematics logging."""

import csv
import json

from backend.math.ocr_service import _cell_boxes_from_metrics
from backend.math.training_log import KINEMATICS_FIELDS, log_kinematics


def _metrics_json(strokes: list[dict]) -> str:
    return json.dumps(
        {
            "cellPx": 48,
            "gridCells": 2,
            "totalStrokes": len(strokes),
            "totalInkLengthPx": 100,
            "totalDrawingTimeMs": 500,
            "eraserEvents": 0,
            "strokesPerCell": {},
            "pauseBetweenStrokesMs": [],
            "strokes": strokes,
        }
    )


def _stroke(idx: int, col: int, bbox: dict, tool: str = "pen") -> dict:
    return {
        "strokeIndex": idx,
        "tool": tool,
        "startTime": 1000 + idx * 500,
        "endTime": 1200 + idx * 500,
        "durationMs": 200,
        "lengthPx": 42.5,
        "pointCount": 12,
        "strokeWidth": 3,
        "avgAngleDeg": 85.0,
        "dominantDirection": "vertical",
        "segmentAnglesDeg": [80, 90],
        "gridCell": {"col": col, "row": 0},
        "bbox": bbox,
    }


def test_cell_boxes_from_metrics_groups_by_column():
    metrics = _metrics_json(
        [
            _stroke(0, 0, {"x": 10, "y": 10, "w": 30, "h": 40}),
            _stroke(1, 0, {"x": 20, "y": 5, "w": 25, "h": 50}),
            _stroke(2, 3, {"x": 200, "y": 12, "w": 28, "h": 44}),
        ]
    )
    boxes = _cell_boxes_from_metrics(metrics)
    assert len(boxes) == 2
    # Column 0: union of two strokes
    assert boxes[0] == (10, 5, 45, 55)
    # Column 3 second (sorted left-to-right)
    assert boxes[1] == (200, 12, 228, 56)


def test_cell_boxes_skips_eraser_and_bad_data():
    metrics = _metrics_json(
        [
            _stroke(0, 0, {"x": 10, "y": 10, "w": 30, "h": 40}, tool="eraser"),
            {"tool": "pen", "bbox": {"x": "bad"}, "gridCell": {"col": 1}},
        ]
    )
    assert _cell_boxes_from_metrics(metrics) == []
    assert _cell_boxes_from_metrics(None) == []
    assert _cell_boxes_from_metrics("not json") == []


def test_log_kinematics_writes_rows(tmp_path, monkeypatch):
    import backend.math.training_log as tl

    monkeypatch.setattr(tl, "KINEMATICS_CSV", tmp_path / "DSC_Kinematics.csv")
    metrics = _metrics_json(
        [
            _stroke(0, 0, {"x": 1, "y": 2, "w": 3, "h": 4}),
            _stroke(1, 1, {"x": 5, "y": 6, "w": 7, "h": 8}, tool="eraser"),
        ]
    )
    written = log_kinematics(
        sample_id="s1", user_id=7, context="train", stroke_metrics_json=metrics
    )
    assert written == 2

    with open(tmp_path / "DSC_Kinematics.csv", newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 2
    assert rows[0]["sample_id"] == "s1"
    assert rows[0]["context"] == "train"
    assert rows[0]["tool"] == "pen"
    assert rows[1]["tool"] == "eraser"
    assert rows[0]["grid_col"] == "0"
    assert set(rows[0].keys()) == set(KINEMATICS_FIELDS)


def test_log_kinematics_handles_empty_and_invalid():
    assert log_kinematics(sample_id="x", user_id=1, context="t", stroke_metrics_json=None) == 0
    assert log_kinematics(sample_id="x", user_id=1, context="t", stroke_metrics_json="") == 0
    assert log_kinematics(sample_id="x", user_id=1, context="t", stroke_metrics_json="{}") == 0
    assert log_kinematics(sample_id="x", user_id=1, context="t", stroke_metrics_json="nope") == 0
