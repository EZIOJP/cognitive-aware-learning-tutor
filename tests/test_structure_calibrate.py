"""Structure verify calibration."""

from __future__ import annotations

import json

import backend.math.structure_verify as sv
from backend.math.structure_calibrate import calibrate_structure_thresholds, collect_calibration_samples
from backend.math.structure_verify import StructureThresholds, load_thresholds, save_thresholds, verify_structure


def test_collect_includes_synthetic_bootstrap():
    samples, _ = collect_calibration_samples(rows=[], include_synthetic=True)
    assert len(samples) >= 5
    assert any(s.source == "synthetic" for s in samples)


def _patch_paths(tmp_path, monkeypatch):
    thresh_path = tmp_path / "structure_thresholds.json"
    report_path = tmp_path / "report.json"
    monkeypatch.setattr(sv, "THRESHOLDS_PATH", thresh_path)
    monkeypatch.setattr(
        "backend.math.structure_calibrate.THRESHOLDS_PATH",
        thresh_path,
    )
    monkeypatch.setattr(
        "backend.math.structure_calibrate.CALIBRATION_REPORT_PATH",
        report_path,
    )
    sv.load_thresholds.cache_clear()
    return thresh_path


def test_calibrate_refuses_to_run_on_synthetic_fixtures_alone(tmp_path, monkeypatch):
    """Bootstrap fixtures clear min_samples on their own; they must not rewrite thresholds."""
    thresh_path = _patch_paths(tmp_path, monkeypatch)

    result = calibrate_structure_thresholds(min_samples=5, include_synthetic=True, rows=[])

    assert result.status == "insufficient_real_samples"
    assert result.real_count == 0
    assert not thresh_path.exists()


def test_synthetic_weight_decays_below_real_ink():
    from backend.math.structure_calibrate import _synthetic_weight

    assert _synthetic_weight(0) > 1.0
    assert _synthetic_weight(30) < 1.0
    assert _synthetic_weight(200) < _synthetic_weight(30)


def test_calibrate_improves_or_maintains_score(tmp_path, monkeypatch):
    thresh_path = _patch_paths(tmp_path, monkeypatch)

    result = calibrate_structure_thresholds(
        min_samples=5,
        min_real_samples=0,
        include_synthetic=True,
        rows=[],
    )
    assert result.status == "calibrated"
    assert thresh_path.is_file()
    assert result.score_after >= result.score_before - 0.01
    loaded = json.loads(thresh_path.read_text())
    assert "silence_threshold" in loaded
    assert 0.3 <= loaded["silence_threshold"] <= 0.6


def test_verify_structure_uses_saved_thresholds(tmp_path, monkeypatch):
    thresh_path = tmp_path / "t.json"
    monkeypatch.setattr(sv, "THRESHOLDS_PATH", thresh_path)
    sv.load_thresholds.cache_clear()

    strict = StructureThresholds(
        sup_height_ratio=0.75,
        sup_baseline_offset=0.20,
        silence_threshold=0.42,
    )
    save_thresholds(strict)
    load_thresholds.cache_clear()

    metrics = sv.paths_to_stroke_metrics([[(10, 30), (28, 54)], [(32, 10), (42, 22)]])
    r = verify_structure(r"x^2", metrics, thresholds=strict)
    assert r.geometry.has_superscript
