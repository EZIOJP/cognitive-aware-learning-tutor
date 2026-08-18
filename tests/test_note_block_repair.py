from backend.transcripts.cleanup import sanitize_mermaid_source
from backend.transcripts.mermaid import is_mermaid_likely_broken
from backend.transcripts.note_block_repair import repair_all_blocks
from backend.transcripts.note_document import mermaid_still_broken


def _is_broken_code(content: str) -> bool:
    return content.strip().lower() in {"", "undefined", "null", "[object object]"}


def test_mermaid_edge_label_sanitize():
    raw = "flowchart TD\nB -- No (Blank) --> D(Default to Array Index 0)"
    fixed = sanitize_mermaid_source(raw)
    assert "No (Blank)" in fixed
    assert "Default to Array Index 0" in fixed
    assert fixed.startswith("flowchart TD")


def test_mermaid_still_broken_detects_legacy_edges():
    # Missing diagram header is the only hard lint; Mermaid.js accepts `-- label -->`.
    assert is_mermaid_likely_broken("A -- Yes --> B") is True
    assert mermaid_still_broken("flowchart TD\nA -- Yes --> B") is False
    assert mermaid_still_broken("flowchart TD\nA -->|Yes| B") is False


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
    assert "No (Blank)" in fixed
    assert "flowchart TD" in fixed
    assert any(d["lang"] == "python" for d in details)
