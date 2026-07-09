from backend.transcripts.cleanup import (
    aggressive_prefix_dedup,
    clean_transcript,
    collapse_caption_bursts,
    collapse_live_caption_fragments,
    count_mermaid_blocks,
    dedupe_lines,
    looks_like_live_captions,
    maximal_prefix_dedup,
    normalize_segment,
    postprocess_markdown,
    repair_mermaid_fences,
    strip_llm_meta_preamble,
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


def test_looks_like_live_captions_detects_prefix_growth():
    raw = "\n".join(
        [
            "Hello everyone",
            "Hello everyone welcome",
            "Hello everyone welcome to numpy",
        ]
        * 25
    )
    assert looks_like_live_captions(raw) is True
    assert looks_like_live_captions("First topic here\nSecond topic there\nThird topic ends") is False


def test_clean_transcript_aggressive_collapses_growing_dump():
    raw = "Hey welcome\nother\nHey welcome everyone\nHey welcome everyone today"
    cleaned = clean_transcript(raw, aggressive=True)
    assert "Hey welcome everyone today" in cleaned
    assert cleaned.count("Hey welcome") == 1


def test_collapse_live_caption_orphan_fragments():
    lines = [
        "As part of your post lecture attachments and finally the pause this is",
        "very important",
        "for every.",
        "I cover.",
        "As part of your post, lecture attachments and finally the pause. This is very important for me.",
        "Everybody clear with this slide.",
    ]
    collapsed = collapse_caption_bursts(lines)
    assert collapsed == [
        "As part of your post, lecture attachments and finally the pause. This is very important for me.",
        "Everybody clear with this slide.",
    ]


def test_clean_transcript_joins_lines():
    raw = "um arrays are cool\narrays are cool\nand useful."
    cleaned = clean_transcript(raw)
    assert "arrays are cool" in cleaned
    assert "um" not in cleaned.lower()
    assert "\n" in cleaned


def test_postprocess_strips_preamble():
    raw = "Here's your summary:\n\n## Arrays\n- point one"
    assert postprocess_markdown(raw).startswith("## Arrays")


def test_strip_llm_meta_preamble_chain_of_thought():
    raw = """**Analyze the Request**
The user wants lecture notes.

I will focus on structuring the lecture around general statistical concepts.# Lecture Notes: NumPy

## Module Overview
- arrays are contiguous memory blocks"""
    out = strip_llm_meta_preamble(raw)
    assert out.startswith("# Lecture Notes")
    assert "Analyze the Request" not in out
    assert "## Module Overview" in out


def test_postprocess_strips_gemma_reasoning():
    raw = """*   **Rules Check**
*   Citations required.

Since the provided reference chunks are technical.# Lecture Notes

## Introduction
- point one"""
    assert postprocess_markdown(raw).startswith("# Lecture Notes")


def test_postprocess_strips_confidence_score_inline_heading():
    raw = """## heading for main topic? Yes.
4. 3-5 key points? Yes.

Confidence Score: 5/5## Module Overview

*   First real bullet."""
    out = postprocess_markdown(raw)
    assert out.startswith("## Module Overview")
    assert "Confidence Score" not in out


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
