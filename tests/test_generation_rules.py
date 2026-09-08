"""Tests for permanent generation rules + topic structure pass."""

from backend.transcripts.generation_rules import (
    BANNED_MCQ_STEMS,
    GOOD_MCQ_EXAMPLES,
    quiz_prompt_rules_block,
    rules_summary_for_api,
)
from backend.transcripts.note_topic_structure import (
    ensure_quiz_topic_structure,
    infer_lecture_number,
)
from backend.transcripts.note_topics import parse_note_topics
from backend.transcripts.study_intel import _is_low_quality_mcq
from tests.test_note_topics import L5_SAMPLE


def test_rules_summary_has_l5_examples():
    summary = rules_summary_for_api()
    assert summary["topic_id_format"] == "L{n}-Txx"
    assert summary["quiz_engine"] == "topic_loop"
    assert len(summary["good_examples"]) >= 2
    assert any("L5-T05" in str(ex.get("topic_id", "")) for ex in summary["good_examples"])


def test_quiz_prompt_includes_good_bad_examples():
    block = quiz_prompt_rules_block(section_title="L5-T05 — Unique values")
    assert "topics" in block.lower()
    assert "GOOD" in block
    assert "BAD" in block
    assert "L5-T05" in block


def test_low_quality_lint_uses_banned_stems():
    bad = {
        "question": "Which statement best matches the note section NumPy?",
        "options": ["It relates to: NumPy", "A", "B", "C"],
    }
    assert _is_low_quality_mcq(bad) is True
    good = {
        "question": GOOD_MCQ_EXAMPLES[0]["question"],
        "options": GOOD_MCQ_EXAMPLES[0]["options"],
    }
    assert _is_low_quality_mcq(good) is False
    assert any(stem in "which statement best matches" for stem in BANNED_MCQ_STEMS)


def test_infer_lecture_number_from_path():
    assert infer_lecture_number("data_foundations/lecture_5/notes.md") == 5
    assert infer_lecture_number("lecture5/foo.md") == 5


def test_ensure_topic_structure_idempotent_on_l5_sample():
    out = ensure_quiz_topic_structure(
        L5_SAMPLE,
        note_path="data_foundations/lecture_5/lecture5_pandas_operations_notes.md",
    )
    topics = parse_note_topics(out)
    assert [t.topic_id for t in topics] == ["L5-T05", "L5-T08"]
    again = ensure_quiz_topic_structure(out, lecture_num=5)
    assert parse_note_topics(again) == topics


def test_ensure_topic_structure_converts_decimal_headings():
    note = """# Lecture 3

## 1.1 Vectorization basics

Vectorization means operating on whole arrays without Python loops in NumPy.
This paragraph is long enough to count as a real topic body for quiz generation.

## 1.2 Broadcasting rules

Broadcasting aligns shapes when dimensions differ. More body text here so the
section passes the minimum character threshold used by the topic parser.
"""
    out = ensure_quiz_topic_structure(
        note,
        lecture_num=3,
        note_path="data_foundations/lecture_3/notes.md",
    )
    topics = parse_note_topics(out)
    assert topics
    assert all(t.topic_id.startswith("L3-T") for t in topics)
    assert "Topic Index" in out
