"""Catalog load cache must stay hot-path cheap."""

from __future__ import annotations

from pathlib import Path

from backend.quiz import content_bank as cb


def test_load_catalog_ttl_skips_restamp(tmp_path: Path, monkeypatch):
    root = tmp_path / "questions"
    (root / "math").mkdir(parents=True)
    calls = {"n": 0}
    real = cb._dir_stamp

    def counting(path: Path):
        calls["n"] += 1
        return real(path)

    monkeypatch.setattr(cb, "_dir_stamp", counting)
    cb.invalidate_catalog_cache()
    c1 = cb.load_catalog(root=root)
    c2 = cb.load_catalog(root=root)
    assert c1 is c2
    assert calls["n"] == 1


def test_invalidate_forces_restamp(tmp_path: Path, monkeypatch):
    root = tmp_path / "questions"
    (root / "math").mkdir(parents=True)
    calls = {"n": 0}
    real = cb._dir_stamp

    def counting(path: Path):
        calls["n"] += 1
        return real(path)

    monkeypatch.setattr(cb, "_dir_stamp", counting)
    cb.invalidate_catalog_cache()
    cb.load_catalog(root=root)
    cb.invalidate_catalog_cache()
    cb.load_catalog(root=root)
    assert calls["n"] == 2


def test_bump_questions_invalidates_catalog(monkeypatch):
    from backend.quiz import source_stamp as stamps

    cleared = {"ok": False}

    def fake_invalidate():
        cleared["ok"] = True

    monkeypatch.setattr(cb, "invalidate_catalog_cache", fake_invalidate)
    stamps.bump_questions()
    assert cleared["ok"] is True
