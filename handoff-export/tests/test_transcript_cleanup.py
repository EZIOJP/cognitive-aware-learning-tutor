from backend.transcripts.cleanup import (
    aggressive_prefix_dedup,
    clean_transcript,
    count_mermaid_blocks,
    dedupe_lines,
    maximal_prefix_dedup,
    normalize_segment,
    postprocess_markdown,
    repair_mermaid_fences,
)


def test_normalize_segment_stutter_and_filler():
    assert normalize_segment("hello hello um okay so arrays") == "hello arrays"


def test_dedupe_consecutive_lines():
    assert dedupe_lines(["hello", "hello", "world"]) == ["hello", "world"]


def test_dedupe_prefix_growing():
    assert dedupe_lines(["Hello", "Hello everyone"]) == ["Hello everyone"]


def test_aggressive_prefix_dedup():
    lines = ["Hello", "Hello everyone", "Hello everyone welcome"]
    assert aggressive_prefix_dedup(lines) == ["Hello everyone welcome"]


def test_maximal_prefix_dedup_non_consecutive():
    lines = ["Hello", "other", "Hello everyone welcome"]
    assert maximal_prefix_dedup(lines) == ["other", "Hello everyone welcome"]


def test_clean_transcript_aggressive_collapses_growing_dump():
    raw = "Hey welcome\nother\nHey welcome everyone\nHey welcome everyone today"
    cleaned = clean_transcript(raw, aggressive=True)
    assert "Hey welcome everyone today" in cleaned
    assert cleaned.count("Hey welcome") == 1


def test_clean_transcript_joins_lines():
    raw = "um arrays are cool\narrays are cool\nand useful."
    cleaned = clean_transcript(raw)
    assert "arrays are cool" in cleaned
    assert "um" not in cleaned.lower()


def test_postprocess_strips_preamble():
    raw = "Here's your summary:\n\n## Arrays\n- point one"
    assert postprocess_markdown(raw).startswith("## Arrays")


def test_repair_mermaid_fences_before_heading():
    raw = """```mermaid
flowchart TD
    A --> B
## Next section
- bullet
```"""
    fixed = repair_mermaid_fences(raw)
    assert fixed.count("```mermaid") == 1
    assert "\n```\n## Next section" in fixed
    assert count_mermaid_blocks(fixed) == 1


def test_repair_mermaid_fences_before_code_fence():
    raw = """```mermaid
graph TD
    A --> B
```python
print("hi")
```"""
    fixed = repair_mermaid_fences(raw)
    assert count_mermaid_blocks(fixed) == 1
    assert "```python" in fixed
