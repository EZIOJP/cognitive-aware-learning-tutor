"""Tests for study library intelligence helpers."""

from backend.transcripts.cleanup import repair_mermaid_fences
from backend.transcripts.concept_extract import concepts_to_retrieval_query, extract_concepts
from backend.transcripts.study_intel import (
    drills_to_markdown,
    gap_summary_markdown,
    generate_quiz_items,
    quiz_to_markdown,
    run_gap_analysis,
)


def test_quiz_to_markdown():
    md = quiz_to_markdown(
        [
            {
                "question": "What is NumPy?",
                "options": ["A library", "A snake", "A database"],
                "answer_index": 0,
                "explanation": "Numeric Python",
            }
        ],
        title="Test Quiz",
    )
    assert "# Test Quiz" in md
    assert "What is NumPy?" in md
    assert "**Answer:** A library" in md


def test_drills_to_markdown():
    md = drills_to_markdown(
        [
            {
                "title": "Array basics",
                "language": "python",
                "prompt": "Create an array",
                "starter_code": "import numpy as np\n",
                "hint": "Use np.array",
            }
        ],
    )
    assert "# Code Drills" in md
    assert "```python" in md
    assert "Array basics" in md


def test_gap_summary_markdown():
    gap = {
        "summary": "Notes miss key definitions.",
        "gaps": [
            {
                "topic": "Definitions",
                "lecture_excerpt": "partial",
                "reference_excerpt": "full",
                "severity": "high",
                "suggestion": "Add glossary",
            }
        ],
        "aligned_topics": ["Overview"],
    }
    md = gap_summary_markdown(gap, lecture_title="Lecture", reference_title="Book")
    assert "Gap Analysis" in md
    assert "Definitions" in md
    assert "Overview" in md


def test_template_gap_analysis_without_llm(monkeypatch):
    monkeypatch.setattr("backend.transcripts.study_intel.ollama_available", lambda *_: False)
    result = run_gap_analysis("## Notes\nHello", "## Book\nWorld")
    assert result["source"] == "template"
    assert len(result["gaps"]) >= 1


def test_repair_fences_imported():
    raw = "```mermaid\nA-->B\n## Next\n"
    fixed = repair_mermaid_fences(raw)
    assert fixed.count("```") >= 2


def test_extract_concepts_heuristic_without_llm(monkeypatch):
    monkeypatch.setattr("backend.transcripts.concept_extract.ollama_available", lambda *_: False)
    concepts = extract_concepts(
        "## Eigenvalues\n## Dot product\n## Topics covered\n",
        topic="Linear Algebra",
        max_concepts=5,
    )
    assert concepts
    assert any("Eigen" in c or "Dot" in c or "Linear" in c for c in concepts)


def test_concepts_to_retrieval_query():
    q = concepts_to_retrieval_query(["eigenvalue", "eigenvector"], topic="LA")
    assert "LA" in q
    assert "eigenvalue" in q


def test_generate_quiz_items_per_concept(monkeypatch):
    monkeypatch.setattr("backend.transcripts.study_intel.ollama_available", lambda *_: True)
    monkeypatch.setattr(
        "backend.transcripts.concept_extract.extract_concepts",
        lambda *a, **k: ["NumPy arrays", "dtype"],
    )
    calls: list[str] = []

    def fake_generate(prompt, **kwargs):
        calls.append(prompt)
        if "NumPy arrays" in prompt:
            return (
                '{"question":"Q1?","options":["A","B","C","D"],'
                '"answer_index":0,"explanation":"e","source_chunk_id":"","concept":"NumPy arrays"}'
            )
        return (
            '{"question":"Q2?","options":["A","B","C","D"],'
            '"answer_index":1,"explanation":"e","source_chunk_id":"","concept":"dtype"}'
        )

    monkeypatch.setattr("backend.transcripts.study_intel.ollama_generate", fake_generate)
    monkeypatch.setattr(
        "backend.transcripts.study_intel._combined_source_material",
        lambda *a, **k: ("## Notes\nNumPy dtype", []),
    )
    result = generate_quiz_items(["## Notes"], count=2, topic="NumPy")
    assert len(result["questions"]) == 2
    concepts = {q.get("concept") for q in result["questions"]}
    assert "NumPy arrays" in concepts
    assert "dtype" in concepts
    assert len(calls) == 2
