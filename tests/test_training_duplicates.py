"""Duplicate cleanup for training samples."""

from __future__ import annotations

import pytest

from backend.math.training_log import append_sample, cleanup_duplicates, find_duplicates


@pytest.fixture
def isolated_training_csv(tmp_path, monkeypatch):
    csv_path = tmp_path / "DSC_handwriting_dataset.csv"
    train_dir = tmp_path / "training"
    train_dir.mkdir()
    monkeypatch.setattr("backend.math.training_log.DATASET_CSV", csv_path)
    monkeypatch.setattr("backend.math.training_log.TRAINING_DIR", train_dir)
    return csv_path


def test_cleanup_duplicates_keeps_oldest(isolated_training_csv):
    append_sample(
        {
            "sample_id": "old",
            "timestamp": "2026-01-01T00:00:00Z",
            "user_id": 1,
            "prompt_id": "d1",
            "confirmed_latex": "1",
            "png_path": "",
        }
    )
    append_sample(
        {
            "sample_id": "new",
            "timestamp": "2026-02-01T00:00:00Z",
            "user_id": 1,
            "prompt_id": "d1",
            "confirmed_latex": "1",
            "png_path": "",
        }
    )
    assert find_duplicates(1)["total_groups"] == 1
    result = cleanup_duplicates(user_id=1)
    assert result["deleted"] == 1
    assert result["groups_cleaned"] == 1
    remaining = find_duplicates(1)
    assert remaining["total_groups"] == 0
