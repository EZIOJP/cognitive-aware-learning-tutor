"""Tests for study library intelligence helpers."""

from backend.transcripts.cleanup import repair_mermaid_fences
from backend.transcripts.study_intel import (
    drills_to_markdown,
    gap_summary_markdown,
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
