from backend.transcripts.cleanup import (
    dedupe_h2_sections,
    postprocess_markdown,
    repair_split_code_fences,
    sanitize_mermaid_blocks,
)


def test_dedupe_h2_sections_keeps_first_only():
    raw = """# Title

## NumPy intro
First version.

## NumPy intro
Duplicate block.

## Pandas
Other topic.
"""
    out = dedupe_h2_sections(raw)
    assert out.count("## NumPy intro") == 1
    assert "First version" in out
    assert "Duplicate block" not in out
    assert "## Pandas" in out


def test_repair_split_code_fences():
    raw = """```python
```
import numpy as np
```
"""
    fixed = repair_split_code_fences(raw)
    assert "```python\nimport numpy" in fixed
    assert fixed.count("```python") == 1


def test_sanitize_mermaid_parentheses_in_diamond():
    raw = """```mermaid
graph TD
    B --> C{Exploratory Data Analysis (EDA)};
    C --> D[Feature Engineering];
```"""
    fixed = sanitize_mermaid_blocks(raw)
    assert "(EDA)" not in fixed or '["Exploratory Data Analysis - EDA"]' in fixed
    assert "{Exploratory" not in fixed


def test_postprocess_dedupes_repeated_sections():
    section = """## Lecture 1: Intro

Some notes here.
"""
    raw = f"# Doc\n\n{section}\n\n{section}"
    out = postprocess_markdown(raw)
    assert out.count("## Lecture 1: Intro") == 1
