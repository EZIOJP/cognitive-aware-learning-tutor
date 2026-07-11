"""Tests for lecture pedagogy filter and RAG hit gate."""

from __future__ import annotations

from backend.transcripts.pedagogy_filter import (
    filter_hits_for_lecture,
    has_technical_substance,
    hit_matches_query,
    is_pure_filler,
    should_keep_transcript_span,
)


def test_drop_thumbs_up() -> None:
    assert is_pure_filler("Please give a thumbs up if you can hear me.")
    assert not should_keep_transcript_span("Please give a thumbs up if you can hear me.")


def test_keep_astype_qa() -> None:
    span = (
        "vishwas question is it doesn't change the original array... "
        "Yes. No no it will not... unless and until I overwrite it like this "
        "and save it back again with astype"
    )
    assert has_technical_substance(span)
    assert should_keep_transcript_span(span)


def test_keep_shape_tuple() -> None:
    span = (
        "Shape function is giving tuple output... for a 2D array or 3D array "
        "the shape will keep on increasing right? So that's why they're showing "
        "up in a couple format."
    )
    assert should_keep_transcript_span(span)


def test_hit_gate_rejects_captioning_for_numpy_query() -> None:
    query = "numpy array shape dtype astype contiguous memory"
    bad = {
        "chunk_id": "ai1",
        "citation": "Artificial Intelligence: A Guide for Thinking Humans",
        "raw_payload": (
            "Image captioning involves generating textual descriptions for images "
            "using CNN and RNN models for accessibility."
        ),
    }
    good = {
        "chunk_id": "np1",
        "citation": "Data Science from Scratch",
        "raw_payload": (
            "NumPy arrays are homogeneous and store values in contiguous memory. "
            "The shape attribute returns a tuple of dimensions. Use astype to convert dtype."
        ),
    }
    assert not hit_matches_query(bad, query)
    assert hit_matches_query(good, query)
    kept = filter_hits_for_lecture([bad, good], query)
    assert len(kept) == 1
    assert kept[0]["chunk_id"] == "np1"
