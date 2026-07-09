"""Tests for narrative quality heuristics."""

from backend.transcripts.coherence import parse_semantic_response, resolve_coherence_mode
from backend.transcripts.narrative_audit import narrative_quality_report


def test_parse_semantic_response_splits_glossary():
    raw = "## Intro\n\nParagraph one.\n\n### Semantic Glossary\n- term: def"
    notes, glossary = parse_semantic_response(raw)
    assert notes.startswith("## Intro")
    assert "Semantic Glossary" in glossary


def test_resolve_coherence_mode_defaults_compact():
    assert resolve_coherence_mode(None) == "compact"
    assert resolve_coherence_mode("auto", llm_tier="heavy") == "cloud_heavy"


def test_narrative_quality_penalizes_bullet_dump():
    body = "\n".join(["- fact " + str(i) for i in range(20)])
    audit = narrative_quality_report(body)
    assert audit.score <= 3
    assert audit.marker == "NARRATIVE_LOW"


def test_narrative_quality_accepts_prose():
    body = "## Topic\n\nTherefore the instructor explained the concept in detail. For example, arrays store elements."
    audit = narrative_quality_report(body)
    assert audit.score >= 3
