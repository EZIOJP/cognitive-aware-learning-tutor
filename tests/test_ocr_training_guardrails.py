"""Guardrails that must hold before any OCR retrain: dedup, holdout, snapshots."""

from __future__ import annotations

from backend.math import artifacts, training_log
from backend.math.holdout import split_rows
from backend.math.mathwriting_import import _dedupe_key, strokes_to_paths_json


def _rows(n: int) -> list[dict]:
    return [{"sample_id": f"sample-{i}"} for i in range(n)]


def test_mathwriting_dedupe_key_matches_the_csv_format(tmp_path):
    """
    The import compares its key against training_log's, so the formats must agree.

    They previously did not, which made cross-run duplicate detection a no-op.
    """
    paths_json = strokes_to_paths_json([[(1.0, 2.0), (3.0, 4.0)], [(5.0, 6.0)]])
    paths_file = tmp_path / "sample.paths.json"
    paths_file.write_text(paths_json, encoding="utf-8")

    label = r"\frac{1}{2}"
    row = {
        "prompt_id": "mw-abc123",
        "confirmed_latex": label,
        "paths_json_path": str(paths_file),
    }

    expected = training_log._sample_dedupe_key(row)
    actual = _dedupe_key("mw-abc123", training_log._normalize_latex(label), paths_json)
    assert actual == expected


def test_dedupe_key_separates_same_label_with_different_ink(tmp_path):
    """Two people writing the same symbol are diversity, not duplicates."""
    first = strokes_to_paths_json([[(0.0, 0.0), (10.0, 10.0)]])
    second = strokes_to_paths_json([[(0.0, 0.0), (10.0, 11.0)]])
    assert _dedupe_key("mw-a", "x", first) != _dedupe_key("mw-a", "x", second)
    assert _dedupe_key("mw-a", "x", first) == _dedupe_key("mw-a", "x", first)


def test_holdout_split_is_disjoint_and_non_empty():
    rows = _rows(300)
    train, held = split_rows(rows, fraction=0.2)

    assert len(train) + len(held) == 300
    train_ids = {r["sample_id"] for r in train}
    held_ids = {r["sample_id"] for r in held}
    assert not (train_ids & held_ids)
    assert 0 < len(held) < 300


def test_holdout_membership_does_not_shift_as_dataset_grows():
    """A sample must never migrate from holdout into training as rows accumulate."""
    rows = _rows(300)
    _, held_early = split_rows(rows[:100], fraction=0.2)
    _, held_later = split_rows(rows, fraction=0.2)

    assert {r["sample_id"] for r in held_early} <= {r["sample_id"] for r in held_later}


def test_snapshot_preserves_previous_version_and_prunes(tmp_path, monkeypatch):
    monkeypatch.setattr(artifacts, "SNAPSHOT_DIR", tmp_path / "snaps")
    target = tmp_path / "model.json"

    target.write_text("v1", encoding="utf-8")
    first = artifacts.snapshot_artifact(target)
    assert first is not None
    assert first.read_text(encoding="utf-8") == "v1"

    target.write_text("v2", encoding="utf-8")
    artifacts.snapshot_artifact(target)
    assert len(artifacts.list_snapshots(target)) == 2

    for i in range(6):
        target.write_text(f"v{i + 3}", encoding="utf-8")
        artifacts.snapshot_artifact(target, keep=3)
    assert len(artifacts.list_snapshots(target)) == 3


def test_snapshot_of_missing_file_is_a_noop(tmp_path, monkeypatch):
    monkeypatch.setattr(artifacts, "SNAPSHOT_DIR", tmp_path / "snaps")
    assert artifacts.snapshot_artifact(tmp_path / "never-written.json") is None


def test_restore_latest_rolls_back(tmp_path, monkeypatch):
    monkeypatch.setattr(artifacts, "SNAPSHOT_DIR", tmp_path / "snaps")
    target = tmp_path / "thresholds.json"

    target.write_text("good", encoding="utf-8")
    artifacts.snapshot_artifact(target)
    target.write_text("bad", encoding="utf-8")

    assert artifacts.restore_latest(target) is not None
    assert target.read_text(encoding="utf-8") == "good"


def test_export_excludes_holdout_rows_from_training(tmp_path, monkeypatch):
    """Held-out samples belong in val/, never in the fine-tune's train/."""
    from PIL import Image

    from backend.math import retrain_service

    monkeypatch.setattr(retrain_service, "FINETUNE_ROOT", tmp_path / "finetune")
    monkeypatch.setattr(retrain_service, "TRAIN_DIR", tmp_path / "finetune" / "train")
    monkeypatch.setattr(retrain_service, "IMAGES_DIR", tmp_path / "finetune" / "train" / "images")
    monkeypatch.setattr(
        retrain_service, "FORMULAS_JSONL", tmp_path / "finetune" / "train" / "formulas.jsonl"
    )
    monkeypatch.setattr(retrain_service, "VAL_DIR", tmp_path / "finetune" / "val")
    monkeypatch.setattr(retrain_service, "VAL_IMAGES_DIR", tmp_path / "finetune" / "val" / "images")
    monkeypatch.setattr(
        retrain_service, "VAL_FORMULAS_JSONL", tmp_path / "finetune" / "val" / "formulas.jsonl"
    )
    monkeypatch.setattr(retrain_service, "MANIFEST_JSON", tmp_path / "finetune" / "manifest.json")

    rows = []
    for i in range(40):
        sample_id = f"sample-{i}"
        png = tmp_path / f"{sample_id}.png"
        Image.new("RGB", (8, 8), "white").save(png)
        rows.append(
            {
                "sample_id": sample_id,
                "confirmed_latex": "x + 1",
                "png_path": str(png),
            }
        )

    _, held = split_rows(rows)
    result = retrain_service.export_texteller_dataset(min_samples=5, rows=rows)

    assert result.status == "exported"
    assert result.holdout_count == len(held)
    assert result.exported == len(rows) - len(held)

    held_ids = {r["sample_id"] for r in held}
    train_images = {p.stem for p in (tmp_path / "finetune" / "train" / "images").glob("*.png")}
    assert not (train_images & held_ids)
