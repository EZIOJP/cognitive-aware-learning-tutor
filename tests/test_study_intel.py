"""Tests for study library intelligence helpers."""

from pathlib import Path

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


def test_expand_quiz_source_paths_adds_siblings_when_short(tmp_path, monkeypatch):
    from backend.transcripts import study_intel as si
    from backend.transcripts import library as lib

    folder = tmp_path / "lecture_2"
    folder.mkdir()
    (folder / "short.md").write_text("## Tiny\n- a\n", encoding="utf-8")
    (folder / "long_a.md").write_text("x" * 500 + "\n## Long A\n", encoding="utf-8")
    (folder / "long_b.md").write_text("y" * 400 + "\n## Long B\n", encoding="utf-8")

    monkeypatch.setattr(si, "resolve_notes_path", lambda rel: tmp_path / rel.replace("\\", "/"))
    monkeypatch.setattr(lib, "NOTES_DIR", tmp_path)
    monkeypatch.setattr(
        si,
        "list_notes_in_folder",
        lambda folder_path, recursive=False: [
            "lecture_2/short.md",
            "lecture_2/long_a.md",
            "lecture_2/long_b.md",
        ],
    )

    paths = si.expand_quiz_source_paths(["lecture_2/short.md"], min_chars=800, max_files=8)
    assert paths[0] == "lecture_2/short.md"
    assert "lecture_2/long_a.md" in paths
    assert len(paths) >= 2


def test_expand_quiz_source_paths_skips_when_enough(tmp_path, monkeypatch):
    from backend.transcripts import study_intel as si

    folder = tmp_path / "lecture_2"
    folder.mkdir()
    (folder / "full.md").write_text("z" * 1200, encoding="utf-8")
    (folder / "other.md").write_text("other", encoding="utf-8")
    monkeypatch.setattr(si, "resolve_notes_path", lambda rel: tmp_path / rel.replace("\\", "/"))

    paths = si.expand_quiz_source_paths(["lecture_2/full.md"], min_chars=800)
    assert paths == ["lecture_2/full.md"]


def test_expand_keeps_multi_select_order(tmp_path, monkeypatch):
    from backend.transcripts import study_intel as si

    folder = tmp_path / "f"
    folder.mkdir()
    (folder / "a.md").write_text("a" * 100, encoding="utf-8")
    (folder / "b.md").write_text("b" * 100, encoding="utf-8")
    monkeypatch.setattr(si, "resolve_notes_path", lambda rel: tmp_path / rel.replace("\\", "/"))
    # Combined still short — will try siblings but both already selected
    monkeypatch.setattr(si, "list_notes_in_folder", lambda *a, **k: ["f/a.md", "f/b.md"])
    paths = si.expand_quiz_source_paths(["f/b.md", "f/a.md"], min_chars=50)
    assert paths[0] == "f/b.md"
    assert paths[1] == "f/a.md"


def test_generate_quiz_items_batch_prompt_is_connecting(monkeypatch):
    monkeypatch.setattr("backend.transcripts.study_intel.ollama_available", lambda *_: True)
    calls: list[str] = []

    def fake_generate(prompt, **kwargs):
        calls.append(prompt)
        if "CODING" in prompt.upper() and "API practice" in prompt:
            return (
                '{"questions":[{"question":"Which call reshapes in place?",'
                '"options":["A","B","C","D"],"answer_index":1,'
                '"explanation":"e","hint":"API","concept":"dtype"}]}'
            )
        return (
            '{"questions":[{"question":"Why prefer contiguous arrays?",'
            '"options":["A","B","C","D"],"answer_index":0,'
            '"explanation":"e","hint":"memory","concept":"NumPy arrays"}]}'
        )

    monkeypatch.setattr("backend.transcripts.study_intel.ollama_generate", fake_generate)
    monkeypatch.setattr(
        "backend.transcripts.study_intel._combined_source_material",
        lambda *a, **k: ("## Notes\nNumPy dtype", []),
    )
    result = generate_quiz_items(["## Notes"], count=2, topic="NumPy", focus="mixed")
    assert len(result["questions"]) == 2
    concepts = {q.get("concept") for q in result["questions"]}
    assert "NumPy arrays" in concepts
    assert "dtype" in concepts
    assert result["source"] == "llm"
    # mixed focus → concept batch + coding batch
    assert len(calls) == 2
    assert result["call_plan"] == [{"role": "concept", "count": 1}, {"role": "coding", "count": 1}]
    joined = " ".join(calls).lower()
    assert "material" in joined
    assert "bland" in joined or "what is x" in joined
    assert "connect" in joined or "coding" in joined


def test_quiz_call_plan_caps_batches():
    from backend.transcripts.study_intel import _quiz_call_plan

    plan = _quiz_call_plan(14, "mixed")
    assert all(c <= 6 for _, c in plan)
    assert sum(c for _, c in plan) == 14
    assert plan[0][0] == "concept"
    assert any(r == "coding" for r, _ in plan)


def test_quiz_call_plan_cover_all_has_connect():
    from backend.transcripts.study_intel import _quiz_call_plan, _split_note_sections

    plan = _quiz_call_plan(30, "cover_all")
    assert sum(c for _, c in plan) == 30
    assert any(r == "connect" for r, _ in plan)
    assert any(r == "concept" for r, _ in plan)
    assert any(r == "coding" for r, _ in plan)
    assert any(r == "definition" for r, _ in plan)
    assert all(c <= 6 for _, c in plan)

    sections = _split_note_sections(
        "## Alpha\n" + ("fact about alpha. " * 20) + "\n## Beta\n" + ("fact about beta. " * 20)
    )
    assert len(sections) >= 2
    assert any("Alpha" in h or h == "Alpha" for h, _ in sections)


def test_cover_all_retries_until_target_count(monkeypatch):
    """Partial LLM batches must be retried until count=30 is filled."""
    monkeypatch.setattr("backend.transcripts.study_intel.ollama_available", lambda *_: True)
    calls: list[str] = []

    def fake_generate(prompt, **kwargs):
        calls.append(prompt)
        i = len(calls)
        return (
            '{"questions":['
            f'{{"question":"Why batch-{i}-a matters for memory?","options":["A","B","C","D"],'
            f'"answer_index":0,"explanation":"e","hint":"h","concept":"c{i}a"}},'
            f'{{"question":"How does batch-{i}-b change indexing?","options":["A","B","C","D"],'
            f'"answer_index":1,"explanation":"e","hint":"h","concept":"c{i}b"}}'
            "]}"
        )

    monkeypatch.setattr("backend.transcripts.study_intel.ollama_generate", fake_generate)
    note = (
        "## Alpha\n"
        + ("contiguous memory enables vectorized ops. " * 30)
        + "\n## Beta\n"
        + ("fancy indexing returns a copy. " * 30)
        + "\n## Gamma\n"
        + ("IndexError when out of bounds. " * 30)
    )
    result = generate_quiz_items([note], count=30, topic="NumPy", focus="cover_all")
    assert result["filled_count"] == 30
    assert result["target_count"] == 30
    assert len(result["questions"]) == 30
    assert result["llm_calls"] >= 5
    assert result["questions_from_llm"] == 30
    assert result["questions_from_extractive"] == 0
    assert result["source"] == "llm"
    assert len(calls) == result["llm_calls"]
    assert result["sections_covered"]


def test_parse_pasted_mcq_quiz_gfg_style():
    from backend.transcripts.study_intel import parse_pasted_mcq_quiz

    text = """
Question 1
How do you create a NumPy array?
A) np.array([1,2])
B) list(1,2)
C) dict()
D) set()
Answer: A

Question 2
Which Pandas method writes CSV?
A) save_csv
B) to_csv
C) write_csv
D) dump_csv
Answer: B
"""
    qs = parse_pasted_mcq_quiz(text)
    assert len(qs) == 2
    assert "NumPy" in qs[0]["question"] or "np.array" in qs[0]["options"][0]
    assert qs[0]["answer_index"] == 0
    assert qs[1]["answer_index"] == 1
    assert qs[0].get("concept")
    assert qs[0].get("hint")


def test_generate_quiz_items_extractive_without_llm(monkeypatch):
    monkeypatch.setattr("backend.transcripts.study_intel.ollama_available", lambda *_: False)
    note = (
        "## NumPy arrays\n"
        "NumPy arrays are typically faster than Python lists because contiguous homogeneous memory "
        "enables vectorized operations.\n"
        "## Indexing\n"
        "Indexing returns a NumPy scalar type such as np.int64, not a plain Python int.\n"
        "## Errors\n"
        "Direct indexing outside the array bounds raises an IndexError.\n"
    )
    result = generate_quiz_items([note], count=3, topic="NumPy")
    assert result["source"] == "extractive"
    assert len(result["questions"]) == 3
    joined = " ".join(q["question"] for q in result["questions"])
    assert "completes this claim" not in joined.casefold()
    assert any(word in joined for word in ("faster", "IndexError", "np.int64", "NumPy", "index"))
    assert all(len(q["options"]) >= 2 for q in result["questions"])


def test_extractive_quiz_uses_note_facts_and_deduplicates(monkeypatch):
    monkeypatch.setattr("backend.transcripts.study_intel.ollama_available", lambda *_: False)
    section = """# full lenght 2
## Exploratory Data Analysis (EDA)
The primary objective of EDA is not to prove a hypothesis, but to understand structure and relationships.
* **Pandas:** Used for data manipulation and transforming data structures (cleaning, filtering).
* **NumPy:** Used for efficient numerical operations on arrays.
## NumPy Arrays and Numerical Operations
NumPy is faster than Python lists because homogeneous contiguous memory enables vectorized operations.
## Array Indexing and Operations
NumPy indexing starts at 0. The third value in W is accessed using `W[2]`.
In NumPy slicing array[start:end], end is always excluded.
An index outside the array range raises an `IndexError`.
"""
    result = generate_quiz_items([section + "\n" + section], count=5, topic="NumPy")
    questions = result["questions"]
    prompts = [q["question"] for q in questions]
    combined = " ".join(
        prompts + [str(option) for q in questions for option in q["options"]]
    )

    assert len(questions) == 5
    assert len({p.casefold() for p in prompts}) == 5
    assert "full lenght 2" not in combined.casefold()
    assert "Which statement best matches" not in combined
    assert "It relates to:" not in combined
    assert "completes this claim" not in combined.casefold()
    assert any(term in combined for term in ("Pandas", "W[2]", "IndexError", "faster", "contiguous", "EDA"))


def test_extractive_quiz_rejects_outline_cloze_junk(monkeypatch):
    monkeypatch.setattr("backend.transcripts.study_intel.ollama_available", lambda *_: False)
    note = Path("data/notes/lecture_2/numpy_lecture_notes.md").read_text(encoding="utf-8")
    result = generate_quiz_items([note], count=5, topic="NumPy")
    combined = " ".join(
        [q["question"] for q in result["questions"]]
        + [str(option) for q in result["questions"] for option in q["options"]]
    ).casefold()
    assert len(result["questions"]) == 5
    assert "completes this claim" not in combined
    assert "____" not in combined
    assert "description" not in combined.split()
    assert "why they matter" not in combined
    assert any(
        phrase in combined
        for phrase in (
            "faster",
            "indexerror",
            "np.int64",
            "excluded",
            "fancy indexing",
            "negative",
        )
    )


def test_quiz_rejects_bland_llm_items_and_uses_fact_fallback(monkeypatch):
    monkeypatch.setattr("backend.transcripts.study_intel.ollama_available", lambda *_: True)
    monkeypatch.setattr(
        "backend.transcripts.study_intel.ollama_generate",
        lambda *a, **k: (
            '{"questions":[{"question":"Which statement best matches the note section NumPy?",'
            '"options":["It relates to: NumPy","Pandas","EDA","Indexing"],'
            '"answer_index":0,"concept":"NumPy"}]}'
        ),
    )
    note = """## NumPy speed
NumPy is faster than Python lists because contiguous homogeneous memory enables vectorized operations.
## Indexing
The third value in W is accessed with `W[2]`.
"""
    result = generate_quiz_items([note], count=2, topic="NumPy")
    combined = " ".join(
        [q["question"] for q in result["questions"]]
        + [str(option) for q in result["questions"] for option in q["options"]]
    )
    assert len(result["questions"]) == 2
    assert "Which statement best matches" not in combined
    assert "It relates to:" not in combined
    assert "W[2]" in combined or "vectorized" in combined


def test_combined_source_never_drops_notes_when_corpus_hits(monkeypatch):
    monkeypatch.setattr(
        "backend.transcripts.study_intel._corpus_hits_for_topic",
        lambda *a, **k: [{"chunk_id": "c1", "citation": "[Book]", "raw_payload": "textbook eigen"}],
    )
    from backend.transcripts.study_intel import _combined_source_material

    # Default: corpus disabled for study intel — notes only
    text, hits = _combined_source_material(
        ["## My lecture notes\n- eigenvalues"],
        topic="eigenvalues",
        prefer_notes=False,
    )
    assert "My lecture notes" in text
    assert "textbook" not in text
    assert hits == []

    # Opt-in merge still keeps notes
    text2, hits2 = _combined_source_material(
        ["## My lecture notes\n- eigenvalues"],
        topic="eigenvalues",
        prefer_notes=False,
        use_corpus=True,
    )
    assert "My lecture notes" in text2
    assert hits2
