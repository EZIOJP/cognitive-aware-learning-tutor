"""Tests for finalize_full_note lint gating behavior."""

from backend.transcripts.chunk_polish import finalize_full_note


def test_finalize_full_note_marks_lint_failures_when_unresolved():
    raw = """# Broken note

```python
def broken(:
    return 1
```
"""
    out = finalize_full_note(raw, repair_blocks=True, use_llm_repair=False, llm=None)
    assert "LINT_FAILED: block" in out


def test_finalize_full_note_no_lint_comment_for_valid_python():
    raw = """# Valid note

```python
import math
print(math.sqrt(9))
```
"""
    out = finalize_full_note(raw, repair_blocks=True, use_llm_repair=False, llm=None)
    assert "LINT_FAILED: block" not in out


def test_finalize_full_note_annotates_when_llm_retry_unavailable(monkeypatch):
    raw = """# Broken note

```python
def broken(:
    return 1
```
"""
    monkeypatch.setattr(
        "backend.transcripts.note_block_repair.repair_all_blocks",
        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("llm unavailable")),
    )
    out = finalize_full_note(raw, repair_blocks=False, llm=None)
    assert "LINT_FAILED: block" in out
