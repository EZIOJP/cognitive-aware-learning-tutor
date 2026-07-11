"""Lecture Auto orchestrator tests."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from transcript_studio.config import AppConfig
from transcript_studio.lecture_auto import run_lecture_auto


@pytest.fixture()
def cfg(tmp_path: Path) -> AppConfig:
    c = AppConfig()
    c.transcripts_dir = str(tmp_path / "transcripts")
    c.notes_dir = str(tmp_path / "notes")
    c.lecture_auto_idle_sec = 600.0
    c.lecture_auto_max_sec = 7500.0
    c.lecture_auto_use_rag = True
    c.lecture_auto_fast_mode = False
    c.lecture_auto_handoff_corpus = False
    return c


def test_lecture_auto_success_pipeline(cfg: AppConfig, tmp_path: Path, monkeypatch):
    transcript = tmp_path / "transcripts" / "live_captions_test.txt"
    transcript.parent.mkdir(parents=True)
    note = tmp_path / "notes" / "lecture.md"
    note.parent.mkdir(parents=True)
    note.write_text("# Notes", encoding="utf-8")

    class FakeScraper:
        segments = ["hello numpy", "arrays and indexing"]

        def run(self, **kwargs):
            return self.segments

        def save(self, output_dir=None):
            transcript.write_text("hello numpy\narrays", encoding="utf-8")
            return transcript

    monkeypatch.setattr("transcript_studio.lecture_auto.llm_generate_reachable", lambda _c: True)
    monkeypatch.setattr("transcript_studio.lecture_auto.check_captions_deps", lambda: (True, "ok"))
    monkeypatch.setattr("transcript_studio.lecture_auto.ensure_windows", lambda: None)
    monkeypatch.setattr("transcript_studio.lecture_auto.LiveCaptionsScraper", lambda **kw: FakeScraper())
    monkeypatch.setattr("transcript_studio.lecture_auto.tune_transcript", lambda *a, **k: "hello numpy arrays")
    monkeypatch.setattr(
        "transcript_studio.lecture_auto.generate_notes_from_file",
        lambda *a, **k: (note, "# Notes", "hybrid_grounded"),
    )
    monkeypatch.setattr("transcript_studio.lecture_auto.save_config", lambda _c: None)

    result = run_lecture_auto(cfg)
    assert result.success
    assert result.transcript_path == transcript
    assert result.note_path == note
    assert result.mode == "hybrid_grounded"
    assert any(p["phase"] == "done" for p in result.phases)


def test_lecture_auto_fails_without_llm(cfg: AppConfig, monkeypatch):
    monkeypatch.setattr("transcript_studio.lecture_auto.llm_generate_reachable", lambda _c: False)
    result = run_lecture_auto(cfg)
    assert not result.success
    assert "LLM not reachable" in result.error
