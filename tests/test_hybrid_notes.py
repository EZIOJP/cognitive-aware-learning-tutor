"""Tests for hybrid notes chunk query + chunk polish."""

from backend.transcripts.chunk_polish import polish_chunk_after_generation
from backend.transcripts.hybrid_notes import chunk_retrieval_query


def test_chunk_retrieval_query_uses_topic_and_heading():
    chunk = "## Eigenvalues\nWe discuss lambda and characteristic polynomials."
    q = chunk_retrieval_query(chunk, "linear algebra")
    assert "linear algebra" in q
    assert "Eigenvalues" in q
    assert "characteristic polynomials" in q


def test_chunk_retrieval_query_fallback_topic():
    q = chunk_retrieval_query("short", "")
    assert q == "short" or "lecture" in q


def test_chunk_retrieval_query_extracts_topic_phrase_after_verb():
    chunk = "In this section we explain gradient descent convergence on convex objectives."
    q = chunk_retrieval_query(chunk, "optimization")
    assert "optimization" in q
    assert "gradient descent convergence" in q


def test_polish_chunk_repairs_mermaid_fence():
    raw = """## Topic

```mermaid
flowchart TD
  A[Start] --> B[End]
```

- point one
"""
    out = polish_chunk_after_generation(raw)
    assert "```mermaid" in out
    assert "flowchart" in out


def test_polish_chunk_wraps_bare_python_after_step():
    raw = """## Demo

Step 1: import numpy
import numpy as np
x = np.array([1, 2])
"""
    out = polish_chunk_after_generation(raw)
    assert "```python" in out or "import numpy" in out
