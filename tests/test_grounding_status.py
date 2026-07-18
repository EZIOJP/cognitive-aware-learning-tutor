"""Grounding status resolution for notes generate APIs."""

from backend.transcripts.note_generation import resolve_grounding


def _enable_rag(monkeypatch):
    monkeypatch.setattr(
        "backend.transcripts.note_generation.get_settings",
        lambda: type("S", (), {"corpus_grounded_notes": True})(),
    )


def test_resolve_grounding_disabled(monkeypatch):
    monkeypatch.setattr(
        "backend.transcripts.note_generation.get_settings",
        lambda: type("S", (), {"corpus_grounded_notes": False})(),
    )
    status, reason = resolve_grounding("hybrid", {"citations": ["x"]})
    assert status == "degraded"
    assert reason == "corpus_rag_disabled"


def test_resolve_grounding_legacy_is_degraded(monkeypatch):
    _enable_rag(monkeypatch)
    monkeypatch.setattr("backend.transcripts.note_generation.corpus_available", lambda: True)
    status, reason = resolve_grounding("legacy", {})
    assert status == "degraded"
    assert reason == "no_textbook_chunks_retrieved"


def test_resolve_grounding_corpus_down(monkeypatch):
    _enable_rag(monkeypatch)
    monkeypatch.setattr("backend.transcripts.note_generation.corpus_available", lambda: False)
    status, reason = resolve_grounding("hybrid", {"citations": ["x"]})
    assert status == "degraded"
    assert reason == "corpus_unavailable"


def test_resolve_grounding_hybrid_with_citations(monkeypatch):
    _enable_rag(monkeypatch)
    monkeypatch.setattr("backend.transcripts.note_generation.corpus_available", lambda: True)
    status, reason = resolve_grounding(
        "hybrid",
        {"citations": ["chunk-1"], "chunk_count": 2},
    )
    assert status == "grounded"
    assert reason is None


def test_resolve_grounding_hybrid_zero_hits(monkeypatch):
    _enable_rag(monkeypatch)
    monkeypatch.setattr("backend.transcripts.note_generation.corpus_available", lambda: True)
    status, reason = resolve_grounding(
        "hybrid",
        {"citations": [], "chunk_count": 0, "chunk_meta": [{"hit_count": 0}]},
    )
    assert status == "degraded"
    assert reason == "no_textbook_chunks_retrieved"
