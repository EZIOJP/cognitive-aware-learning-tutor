"""Tests for tag_engine.py."""

from __future__ import annotations

import pytest

from transcript_studio.tag_engine import (
    TaggedDraft,
    annotate_draft_with_topics,
    normalize_tags,
    parse_topics_line,
    sort_drafts_by_topic,
    strip_topics_annotations,
)


# ---------------------------------------------------------------------------
# parse_topics_line
# ---------------------------------------------------------------------------


def test_parse_topics_line_basic():
    text = "TOPICS: datascience/numpy/arrays, datascience/numpy/broadcasting"
    tags = parse_topics_line(text)
    assert tags == ["datascience/numpy/arrays", "datascience/numpy/broadcasting"]


def test_parse_topics_line_case_insensitive():
    text = "Topics: Math/Calculus"
    tags = parse_topics_line(text)
    assert tags == ["math/calculus"]


def test_parse_topics_line_no_match():
    assert parse_topics_line("No topics here.") == []


def test_parse_topics_line_semicolon_sep():
    text = "TOPICS: a/b; c/d"
    tags = parse_topics_line(text)
    assert len(tags) == 2


def test_parse_topics_line_spaces_to_underscores():
    text = "TOPICS: data science/numpy arrays"
    tags = parse_topics_line(text)
    assert "data_science/numpy_arrays" in tags


# ---------------------------------------------------------------------------
# normalize_tags
# ---------------------------------------------------------------------------


def test_normalize_tags_merges_synonyms():
    groups = [["numpy/arrays"], ["arrays/numpy"]]
    mapping = normalize_tags(groups, threshold=0.70)
    canon_a = mapping.get("numpy/arrays", "numpy/arrays")
    canon_b = mapping.get("arrays/numpy", "arrays/numpy")
    assert canon_a == canon_b, "Synonym tags should map to same canonical form"


def test_normalize_tags_distinct_tags_stay_separate():
    groups = [["numpy/arrays"], ["matplotlib/plots"]]
    mapping = normalize_tags(groups, threshold=0.80)
    assert mapping["numpy/arrays"] != mapping["matplotlib/plots"]


def test_normalize_tags_empty():
    assert normalize_tags([]) == {}


def test_normalize_tags_single_group():
    # numpy/array and numpy/arrays are very similar strings → should cluster
    groups = [["numpy/array", "numpy/arrays"]]
    mapping = normalize_tags(groups, threshold=0.80)
    # Both should map to the same canonical form
    assert mapping.get("numpy/array") == mapping.get("numpy/arrays")


# ---------------------------------------------------------------------------
# sort_drafts_by_topic
# ---------------------------------------------------------------------------


def test_sort_groups_same_topics_together():
    td1 = TaggedDraft(draft="draft1", tags=["datascience/numpy"])
    td2 = TaggedDraft(draft="draft2", tags=["matplotlib/plots"])
    td3 = TaggedDraft(draft="draft3", tags=["datascience/pandas"])
    tag_map = {"datascience/numpy": "datascience/numpy",
               "matplotlib/plots": "matplotlib/plots",
               "datascience/pandas": "datascience/pandas"}

    sorted_drafts = sort_drafts_by_topic([td1, td2, td3], tag_map)
    # datascience topics should be adjacent
    topics = [d.tags[0] for d in sorted_drafts if d.tags]
    assert topics.index("datascience/numpy") < topics.index("matplotlib/plots") or \
           topics.index("datascience/pandas") < topics.index("matplotlib/plots")


def test_sort_untagged_go_to_end():
    td_tagged = TaggedDraft(draft="tagged", tags=["math/calculus"])
    td_untagged = TaggedDraft(draft="no tags", tags=[])
    tag_map = {"math/calculus": "math/calculus"}

    result = sort_drafts_by_topic([td_untagged, td_tagged], tag_map)
    assert result[-1].tags == []  # untagged always last


# ---------------------------------------------------------------------------
# annotate_draft_with_topics / strip_topics_annotations
# ---------------------------------------------------------------------------


def test_annotate_adds_topics_line():
    td = TaggedDraft(draft="Content here.", tags=["math/algebra"])
    annotated = annotate_draft_with_topics(td)
    assert annotated.startswith("TOPICS: math/algebra")
    assert "Content here." in annotated


def test_annotate_no_tags_unchanged():
    td = TaggedDraft(draft="No topics.", tags=[])
    assert annotate_draft_with_topics(td) == "No topics."


def test_strip_topics_annotations_removes_lines():
    text = "TOPICS: math/algebra\n\nSome content.\n\nTOPICS: cs/algorithms\n\nMore content."
    stripped = strip_topics_annotations(text)
    assert "TOPICS:" not in stripped
    assert "Some content." in stripped
    assert "More content." in stripped


def test_strip_topics_annotations_idempotent():
    text = "Clean content without topics."
    assert strip_topics_annotations(text) == text
