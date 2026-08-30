"""Stroke-symbol retrain from handwriting dataset."""

from __future__ import annotations

import json

import backend.math.stroke_symbol as ss
from backend.math.stroke_symbol import (
    collect_dataset_glyph_samples,
    normalize_glyph_label,
    paths_json_to_strokes,
    train_from_handwriting_dataset,
)


def test_normalize_glyph_label():
    assert normalize_glyph_label("7") == "7"
    assert normalize_glyph_label("x") == "x"
    assert normalize_glyph_label(r"\frac{1}{2}") is None
    assert normalize_glyph_label("12") is None


def test_collect_dataset_glyph_samples(tmp_path):
    paths_file = tmp_path / "s1.paths.json"
    stroke = [{"drawMode": True, "paths": [{"x": 0.1, "y": 0.5}, {"x": 0.9, "y": 0.5}]}]
    paths_file.write_text(json.dumps(stroke), encoding="utf-8")

    rows = [
        {
            "sample_id": "s1",
            "confirmed_latex": "+",
            "paths_json_path": str(paths_file),
        }
    ]
    samples, skip = collect_dataset_glyph_samples(rows=rows)
    assert len(samples) == 1
    assert samples[0][0] == "+"
    assert len(samples[0][1]) == 1


def test_train_from_handwriting_dataset(tmp_path, monkeypatch):
    model_path = tmp_path / "model.npz"
    monkeypatch.setattr(ss, "MODEL_PATH", model_path)
    ss._load_model.cache_clear()

    paths_file = tmp_path / "p.paths.json"
    paths_file.write_text(
        json.dumps([{"drawMode": True, "paths": [{"x": 0.2, "y": 0.5}, {"x": 0.8, "y": 0.5}]}]),
        encoding="utf-8",
    )
    rows = [{"confirmed_latex": "-", "paths_json_path": str(paths_file)}]

    result = train_from_handwriting_dataset(
        min_real_samples=1,
        include_synthetic=True,
        synth_per_class=5,
        path=model_path,
        rows=rows,
    )
    assert result["status"] == "trained"
    assert model_path.exists()
    assert result["real_samples"] == 1

    strokes = paths_json_to_strokes(paths_file.read_text())
    pred = ss.predict_symbol(strokes, min_confidence=0.1)
    assert pred is not None
