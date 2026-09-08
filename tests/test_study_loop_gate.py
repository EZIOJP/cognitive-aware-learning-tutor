"""Study Loop SoftLand gate toggle."""

from __future__ import annotations

from pathlib import Path

from backend.quiz import study_loop_gate as slg


def test_default_off(tmp_path: Path):
    path = tmp_path / "study_loop_gate.json"
    assert slg.is_required(path=path) is False


def test_set_enabled(tmp_path: Path):
    path = tmp_path / "study_loop_gate.json"
    slg.set_enabled(True, path=path)
    assert slg.is_required(path=path) is True
    slg.set_enabled(False, path=path)
    assert slg.is_required(path=path) is False
    assert slg.serialize(path=path)["enabled"] is False
