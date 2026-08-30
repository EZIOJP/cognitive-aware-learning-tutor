"""TexTeller retrain export from DSC_handwriting_dataset.csv."""

from __future__ import annotations

import base64
from io import BytesIO
from pathlib import Path

import pytest
from PIL import Image, ImageDraw

from backend.math.retrain_service import (
    export_texteller_dataset,
    ground_truth_latex,
    resolve_png_path,
)
from backend.paths import ROOT


def test_ground_truth_latex_priority():
    assert ground_truth_latex({"confirmed_latex": "7", "teacher_latex": "8"}) == "7"
    assert ground_truth_latex({"confirmed_latex": "", "teacher_latex": "x+1"}) == "x+1"
    assert ground_truth_latex({"target_latex": "2"}) == "2"
    assert ground_truth_latex({}) == ""


def test_export_insufficient_samples():
    result = export_texteller_dataset(min_samples=5, rows=[])
    assert result.status == "insufficient_samples"
    assert result.exported == 0


def test_export_copies_png_and_writes_jsonl(tmp_path, monkeypatch):
    img = Image.new("RGB", (80, 40), "white")
    ImageDraw.Draw(img).line([(5, 20), (75, 20)], fill="black", width=3)
    buf = BytesIO()
    img.save(buf, format="PNG")
    b64 = base64.b64encode(buf.getvalue()).decode("ascii")

    png_dir = tmp_path / "data_logs" / "training"
    png_dir.mkdir(parents=True)
    png_path = png_dir / "s1.png"
    png_path.write_bytes(base64.b64decode(b64))

    finetune = tmp_path / "finetune"
    train_dir = finetune / "train"
    monkeypatch.setattr("backend.math.retrain_service.FINETUNE_ROOT", finetune)
    monkeypatch.setattr("backend.math.retrain_service.TRAIN_DIR", train_dir)
    monkeypatch.setattr("backend.math.retrain_service.IMAGES_DIR", train_dir / "images")
    monkeypatch.setattr("backend.math.retrain_service.FORMULAS_JSONL", train_dir / "formulas.jsonl")
    monkeypatch.setattr("backend.math.retrain_service.MANIFEST_JSON", finetune / "manifest.json")

    rows = [
        {
            "sample_id": "s1",
            "confirmed_latex": "x+2",
            "png_path": str(png_path),
        }
    ]

    result = export_texteller_dataset(min_samples=1, rows=rows)
    assert result.status == "exported"
    assert result.exported == 1
    assert (train_dir / "images" / "s1.png").is_file()
    jsonl = (train_dir / "formulas.jsonl").read_text(encoding="utf-8")
    assert '"formula": "x+2"' in jsonl
    assert resolve_png_path(rows[0]) == png_path
