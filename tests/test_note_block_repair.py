from backend.transcripts.cleanup import sanitize_mermaid_source
from backend.transcripts.note_block_repair import _is_broken_code, _mermaid_still_broken, repair_all_blocks


def test_mermaid_edge_label_sanitize():
    raw = "B -- No (Blank) --> D(Default to Array Index 0)"
    fixed = sanitize_mermaid_source(raw)
    assert "-->|No (Blank)|" in fixed
    assert 'D["Default to Array Index 0"]' in fixed
    assert 'No["Blank"]' not in fixed


def test_mermaid_still_broken_detects_legacy_edges():
    assert _mermaid_still_broken("A -- Yes --> B") is True
    assert _mermaid_still_broken("A -->|Yes| B") is False


def test_is_broken_code():
    assert _is_broken_code("undefined") is True
    assert _is_broken_code("import numpy as np") is False


def test_repair_all_blocks_sanitize_only(monkeypatch):
    md = """## Topic

```mermaid
flowchart TD
    B -- No (Blank) --> D(Default to 0)
```

```python
undefined
```
"""
    monkeypatch.setattr(
        "backend.transcripts.note_block_repair.ollama_available",
        lambda llm=None: False,
    )
    fixed, details = repair_all_blocks(md, use_llm=False)
    assert "-->|No (Blank)|" in fixed
    assert any(d["lang"] == "mermaid" for d in details)
