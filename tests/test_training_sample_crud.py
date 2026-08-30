"""Training sample list / update / delete."""

from __future__ import annotations

import base64
import json
from io import BytesIO

import pytest
from PIL import Image, ImageDraw

from backend.math.training_log import (
    DATASET_CSV,
    TRAINING_DIR,
    append_sample,
    delete_sample,
    list_samples,
    log_training_sample,
    update_sample,
)


def _fake_png_b64() -> str:
    img = Image.new("RGB", (40, 40), "white")
    ImageDraw.Draw(img).line([(5, 20), (35, 20)], fill="black", width=2)
    buf = BytesIO()
    img.save(buf, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode("ascii")


@pytest.fixture
def isolated_training_csv(tmp_path, monkeypatch):
    csv_path = tmp_path / "DSC_handwriting_dataset.csv"
    train_dir = tmp_path / "training"
    train_dir.mkdir()
    monkeypatch.setattr("backend.math.training_log.DATASET_CSV", csv_path)
    monkeypatch.setattr("backend.math.training_log.TRAINING_DIR", train_dir)
    return csv_path


def test_update_and_delete_sample(isolated_training_csv):
    sid = log_training_sample(
        user_id=1,
        tier="digits",
        prompt_id="d1",
        prompt_text="1",
        canvas_image=_fake_png_b64(),
        predicted_latex="l",
        confirmed_latex="1",
        action="correct",
        paths_json=json.dumps([{"drawMode": True, "paths": [{"x": 0, "y": 0}, {"x": 1, "y": 1}]}]),
    )
    listed = list_samples(1)
    assert listed["total"] == 1

    updated = update_sample(sid, user_id=1, confirmed_latex="1")
    assert updated is not None
    assert updated["confirmed_latex"] == "1"
    assert updated["agree"] == "corrected"

    result = delete_sample(sid, user_id=1)
    assert result["ok"] is True
    assert list_samples(1)["total"] == 0
    assert not isolated_training_csv.read_text(encoding="utf-8").strip().splitlines()[1:]


def test_delete_forbidden_other_user(isolated_training_csv):
    append_sample(
        {
            "sample_id": "x1",
            "user_id": 2,
            "confirmed_latex": "2",
            "png_path": "",
        }
    )
    result = delete_sample("x1", user_id=1)
    assert result["ok"] is False
    assert result["reason"] == "forbidden"
