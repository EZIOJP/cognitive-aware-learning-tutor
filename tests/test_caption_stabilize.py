"""Caption stabilizer — SaveLiveCaptions-inspired quality gates."""

from __future__ import annotations

from backend.transcripts.caption_stabilize import (
    CaptionStabilizer,
    is_better_version,
    is_incomplete_sentence,
    similarity_ratio,
    split_caption_sentences,
    strip_caption_timestamp,
)
from backend.transcripts.cleanup import merge_similar_caption_lines
from backend.transcripts.live_captions import LiveCaptionsScraper


def test_strip_timestamp():
    assert strip_caption_timestamp("[12:34:56] Hello world") == "Hello world"
    assert strip_caption_timestamp("No stamp") == "No stamp"


def test_split_and_incomplete():
    parts = split_caption_sentences("Hello there. We will continue")
    assert parts[0] == "Hello there."
    assert is_incomplete_sentence("We will continue")
    assert not is_incomplete_sentence("We will continue.")


def test_better_version_prefers_longer():
    old = "We cover arrays."
    new = "We cover arrays and linked lists in detail."
    assert similarity_ratio(old, new) >= 0.5
    assert is_better_version(new, old)


def test_stabilizer_waits_for_threshold():
    stab = CaptionStabilizer(stable_threshold=3, min_length=10)
    panel = "Arrays are contiguous memory blocks."
    assert stab.observe_panel(panel) == []
    assert stab.observe_panel(panel) == []
    commits = stab.observe_panel(panel)
    assert len(commits) == 1
    assert commits[0][0] == "append"
    assert "Arrays" in commits[0][1]
    # Already seen — no re-commit
    assert stab.observe_panel(panel) == []


def test_stabilizer_seed_skips_existing_panel():
    stab = CaptionStabilizer(stable_threshold=1, min_length=10)
    panel = "Already on screen before capture started."
    stab.mark_seen_from_panel(panel)
    assert stab.observe_panel(panel) == []


def test_merge_similar_keeps_better():
    lines = [
        "We will study sorting next.",
        "We will study sorting algorithms next week.",
    ]
    out = merge_similar_caption_lines(lines, threshold=0.7)
    assert len(out) == 1
    assert "algorithms" in out[0]


def test_scraper_save_adds_timestamps(tmp_path):
    scraper = LiveCaptionsScraper(timestamps=True)
    scraper._record("First complete sentence about arrays.")
    path = scraper.save(tmp_path / "out.txt")
    text = path.read_text(encoding="utf-8")
    assert text.startswith("[")
    assert "First complete sentence" in text
