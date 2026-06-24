"""Tests for embedding-based topic grouping."""

from unittest.mock import patch

import numpy as np

from backend.transcripts.semantic_grouper import (
    TopicGroup,
    group_transcript,
    groups_from_word_chunks,
    match_reference_chunk,
    segment_transcript,
)


def test_segment_transcript_packs_sentences():
    text = "First sentence here. Second sentence follows. Third one too. Fourth for packing."
    segments = segment_transcript(text, segment_words=8)
    assert len(segments) >= 2
    assert "First sentence" in segments[0]


@patch("backend.transcripts.semantic_grouper.encode_texts")
def test_group_transcript_merges_repeated_topic(mock_encode):
    segments = [
        "Today we cover exploratory data analysis with pandas.",
        "The weather is nice and students are chatting.",
        "Back to EDA — histograms and describe() in pandas.",
    ]
    cleaned = "\n\n".join(segments)
    # Similar vectors for segments 0 and 2; different for segment 1
    mock_encode.return_value = np.array(
        [
            [1.0, 0.0, 0.0],
            [0.0, 1.0, 0.0],
            [0.95, 0.05, 0.0],
        ],
        dtype="float32",
    )

    with patch("backend.transcripts.semantic_grouper.segment_transcript", return_value=segments):
        groups = group_transcript(cleaned, cluster_threshold=0.72)

    assert groups is not None
    assert len(groups) == 2
    assert groups[0].first_index == 0
    merged = groups[0].segment_indices
    assert 0 in merged and 2 in merged


@patch("backend.transcripts.semantic_grouper.encode_texts", return_value=None)
@patch(
    "backend.transcripts.semantic_grouper.segment_transcript",
    return_value=["segment one about numpy", "segment two about pandas", "segment three about plotting"],
)
def test_group_transcript_returns_none_without_embeddings(_mock_segment, mock_encode):
    groups = group_transcript("ignored")
    assert groups is None
    mock_encode.assert_called()


def test_groups_from_word_chunks_fallback():
    text = ". ".join(f"topic sentence number {i}" for i in range(400))
    groups = groups_from_word_chunks(text, target_words=200)
    assert len(groups) >= 2
    assert all(isinstance(g, TopicGroup) for g in groups)


@patch("backend.transcripts.semantic_grouper.encode_texts")
def test_match_reference_chunk_picks_best(mock_encode):
    group = "NumPy array indexing and slicing"
    refs = ["Python list comprehensions", "NumPy ndarray indexing tutorial"]
    mock_encode.return_value = np.array(
        [
            [1.0, 0.0],
            [0.0, 1.0],
            [0.9, 0.1],
        ],
        dtype="float32",
    )
    best = match_reference_chunk(group, refs)
    assert best == refs[1]
