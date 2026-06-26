from transcript_studio.cleanup import (
    aggressive_prefix_dedup,
    clean_transcript,
    count_code_blocks,
    count_mermaid_blocks,
    dedupe_lines,
    maximal_prefix_dedup,
    normalize_segment,
    postprocess_markdown,
    repair_all_fences,
    strip_whole_response_wrapper,
)


def test_normalize_segment_stutter_and_filler():
    assert normalize_segment("hello hello um okay so arrays") == "hello arrays"


def test_dedupe_consecutive_lines():
    assert dedupe_lines(["hello", "hello", "world"]) == ["hello", "world"]


def test_clean_transcript_aggressive():
    raw = "Hey welcome\nother\nHey welcome everyone\nHey welcome everyone today"
    cleaned = clean_transcript(raw, aggressive=True)
    assert "Hey welcome everyone today" in cleaned


def test_postprocess_strips_preamble():
    raw = "Here's your summary:\n\n## Arrays\n- point one"
    assert postprocess_markdown(raw).startswith("## Arrays")


def test_strip_whole_response_wrapper_only_when_wrapped():
    wrapped = "```markdown\n## Title\n\nBody\n```"
    assert strip_whole_response_wrapper(wrapped).startswith("## Title")
    inner = "## Title\n\n```python\nx = 1\n```"
    assert strip_whole_response_wrapper(inner) == inner


def test_repair_all_fences_closes_before_heading():
    raw = """```mermaid
flowchart TD
    A --> B
## Next section
- bullet
```"""
    fixed = repair_all_fences(raw)
    assert count_mermaid_blocks(fixed) == 1


def test_repair_all_fences_python_block():
    raw = """```python
print("hi")
## Oops heading inside block
"""
    fixed = repair_all_fences(raw)
    assert count_code_blocks(fixed) == 1
    assert "## Oops heading inside block" in fixed


def test_postprocess_preserves_multiple_code_blocks():
    raw = """## Topic

```python
a = 1
```

More text.

```mermaid
flowchart LR
    A --> B
```
"""
    fixed = postprocess_markdown(raw)
    assert count_code_blocks(fixed) == 2
    assert count_mermaid_blocks(fixed) == 1
