"""Tests for unified note document module."""

from backend.transcripts.note_document import (
    apply_block_update,
    finalize_note_markdown,
    list_fenced_blocks,
    prepare_note_markdown,
    replace_fenced_block,
)

SAMPLE = """# Test

```mermaid
flowchart TD
    A --> B
```

inline `code`

```python
print(1)
```
"""


def test_list_fenced_blocks_counts_only_fences():
    prepared = prepare_note_markdown(SAMPLE)
    blocks = list_fenced_blocks(prepared)
    assert len(blocks) == 2
    assert blocks[0].lang == "mermaid"
    assert blocks[1].lang == "python"


def test_replace_fenced_block_by_index():
    prepared = prepare_note_markdown(SAMPLE)
    updated = replace_fenced_block(prepared, 0, "flowchart TD\n    X --> Y")
    assert "X --> Y" in updated
    blocks = list_fenced_blocks(updated)
    assert len(blocks) == 2


def test_apply_block_update_mermaid_layout_safe():
    prepared = prepare_note_markdown(SAMPLE)
    updated = apply_block_update(
        prepared,
        0,
        'flowchart TD\n    B -- Yes --> C["arr[i]"]',
        lang="mermaid",
    )
    assert "arr" in updated


def test_finalize_note_markdown():
    raw = "```mermaid\nflowchart TD\nA --> B(W[-1])\n```"
    out = finalize_note_markdown(raw)
    assert "```mermaid" in out
