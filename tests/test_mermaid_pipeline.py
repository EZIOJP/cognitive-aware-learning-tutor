from backend.transcripts.mermaid import (
    aggressive_sanitize_mermaid_source,
    dedupe_headers,
    extract_from_llm,
    is_mermaid_likely_broken,
    mermaid_lint_issues,
    sanitize_mermaid_source,
)


def test_sanitize_stadium_function_calls():
    raw = "A[NumPy Functions] --> B(np.all)"
    fixed = sanitize_mermaid_source(raw)
    assert 'B["np.all"]' in fixed
    assert not is_mermaid_likely_broken(fixed)


def test_sanitize_colon_after_square_label():
    raw = "P[Positive Indexing]: Start Left -> Right"
    fixed = sanitize_mermaid_source(raw)
    assert 'P["Positive Indexing: Start Left -> Right"]' in fixed
    assert not is_mermaid_likely_broken(fixed)


def test_sanitize_malformed_pipe_edge():
    raw = "A[Start Index] -->|: Start:| B(Element at start)"
    fixed = sanitize_mermaid_source(raw)
    assert "-->|Start|" in fixed
    assert 'B["Element at start"]' in fixed
    assert not is_mermaid_likely_broken(fixed)


def test_sanitize_ampersand_with_diamond_target():
    raw = "B & D --> E{Slice Range Determined}"
    fixed = sanitize_mermaid_source(raw)
    assert "B --> E{Slice Range Determined}" in fixed
    assert "D --> E{Slice Range Determined}" in fixed
    assert not is_mermaid_likely_broken(fixed)


def test_sanitize_brace_node_id():
    raw = "N --> n_{-1}(Index -1)"
    fixed = sanitize_mermaid_source(raw)
    assert 'n_1["Index -1"]' in fixed
    assert not is_mermaid_likely_broken(fixed)


def test_ensure_flowchart_header():
    raw = "A[Start] --> B[End]"
    fixed = sanitize_mermaid_source(raw)
    assert fixed.startswith("flowchart TD")


def test_layout_fix_positive_negative_indexing_diagram():
    raw = """flowchart TD
    A[Start Indexing Process] --> B{Direction}
    B -->|Left to Right| C["Positive Index: 0, 1, 2, ..."]
    B -->|Right to Left| D["Negative Index: -1, -2, -3, ..."]
    D --> E["Access Last Element using W[-1]"]
    C --> F["Requires Length Calculation for last element W[len-1]"]"""
    fixed = sanitize_mermaid_source(raw)
    assert "..." not in fixed
    assert "|L to R|" in fixed
    assert "|R to L|" in fixed
    assert "Last at index minus one" in fixed


def test_sanitize_gemma_indexing_diagram_output():
    gemma = """flowchart TD
    A["Start Indexing Process"] --> B{"Direction"}
    B -->|Left to Right| C["Positive Index: 0, 1, etc"]
    B -->|Right to Left| D["Negative Index: -1, -2, etc"]
    D --> E["Access Last Element (W[-1])"]
    C --> F["Need Length Calculation"]"""
    fixed = sanitize_mermaid_source(gemma)
    assert '{"Direction"}' not in fixed
    assert "B{Direction}" in fixed
    assert "W[-1]" not in fixed
    assert "|L to R|" in fixed
    assert not is_mermaid_likely_broken(fixed)


def test_aggressive_sanitize_gemma_output_uses_canonical_indexing_flow():
    gemma = """flowchart TD
A[Start Indexing Process] --> B{Direction}
B -->|L to R| C["Pos Index: 0, 1, 2, etc"]
B -->|R to L| D["Neg Index: -1, -2, -3, etc"]
D --> E["Last Element W[-1]"]
C --> F["Needs Length Calc for last element"]"""
    fixed = aggressive_sanitize_mermaid_source(gemma)
    assert "W[-1]" not in fixed
    assert "Positive indices" in fixed
    assert "Last at index minus one" in fixed
    assert not is_mermaid_likely_broken(fixed)


def test_extract_mermaid_strips_llm_reasoning_preamble():
    raw = (
        "The user wants me to fix a broken Mermaid diagram source.\n"
        "The goal is to produce ONLY the valid Mermaid syntax without explanation.\n"
        "Here is the corrected diagram:\n\n"
        "flowchart TD\n"
        'A["Start Indexing Process"] --> B{Direction}\n'
        'B -->|L to R| C["Positive Index: 0, 1, 2, etc"]\n'
        'D --> E["Get Last Element W[-1]"]'
    )
    extracted = extract_from_llm(raw)
    assert extracted.startswith("flowchart TD")
    assert "The user wants" not in extracted
    fixed = aggressive_sanitize_mermaid_source(raw)
    assert "The user wants" not in fixed
    assert fixed.lower().count("flowchart td") == 1


def test_dedupe_repeated_gemma_diagram_glued():
    """Gemma 4B sometimes repeats flowchart TD without a newline between copies."""
    gemma = (
        'flowchart TD\nA[Start Indexing Process] --> B{Direction}\n'
        'B -->|L to R| C["Positive Index: 0, 1, 2, etc"]\n'
        'B -->|R to L| D["Negative Index: -1, -2, -3, etc"]\n'
        'D --> E["Get Last Element W[-1]"]\n'
        'C --> F["Needs Length Calc for last el"]flowchart TD\n'
        'A[Start Indexing Process] --> B{Direction}\n'
        'B -->|L to R| C["Positive Index: 0, 1, 2, etc"]\n'
        'B -->|R to L| D["Negative Index: -1, -2, -3, etc"]\n'
        'D --> E["Get Last Element W[-1]"]\n'
        'C --> F["Needs Length Calc for last el"]'
    )
    deduped = dedupe_headers(gemma)
    assert deduped.lower().count("flowchart td") == 1
    fixed = aggressive_sanitize_mermaid_source(gemma)
    assert fixed.lower().count("flowchart td") == 1
    assert "Positive indices" in fixed
    assert "W[-1]" not in fixed


def test_lint_catches_legacy_edge():
    issues = mermaid_lint_issues("A -- Yes --> B")
    assert any("legacy" in i for i in issues)
