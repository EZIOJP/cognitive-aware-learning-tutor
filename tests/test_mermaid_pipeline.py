from backend.transcripts.mermaid import (
    dedupe_headers,
    extract_from_llm,
    is_mermaid_likely_broken,
    mermaid_lint_issues,
    sanitize_mermaid_source,
)


def test_sanitize_preserves_source():
    raw = "flowchart TD\nA[NumPy Functions] --> B(np.all)"
    fixed = sanitize_mermaid_source(raw)
    assert fixed == raw
    assert not is_mermaid_likely_broken(fixed)


def test_sanitize_strips_fence_wrappers():
    raw = "```mermaid\nflowchart LR\n  A --> B\n```"
    assert sanitize_mermaid_source(raw) == "flowchart LR\n  A --> B"


def test_sanitize_does_not_replace_direction_index_diagram():
    raw = (
        "flowchart TD\n"
        "    A[Start] --> B{Direction}\n"
        "    B --> C[Index -1]"
    )
    fixed = sanitize_mermaid_source(raw)
    assert "Index -1" in fixed
    assert "Positive indices" not in fixed


def test_extract_from_llm_finds_flowchart():
    raw = "Here you go:\n\nflowchart TD\n  A --> B"
    assert "flowchart TD" in extract_from_llm(raw)


def test_dedupe_headers():
    raw = "flowchart TD\nA --> B\nflowchart TD\nC --> D"
    out = dedupe_headers(raw)
    assert "A --> B" in out
    assert "C --> D" not in out


def test_lint_empty():
    assert mermaid_lint_issues("") == ["empty diagram"]


def test_lint_missing_header():
    assert "missing flowchart/graph header" in mermaid_lint_issues("A --> B")
