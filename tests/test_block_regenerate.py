from backend.transcripts.block_regenerate import regenerate_block, regenerate_selection, _classify_selection, _strip_fences


def test_strip_fences():
    assert _strip_fences("```python\nx=1\n```") == "x=1"
    assert _strip_fences("x=1") == "x=1"


def test_classify_selection_mermaid_fence():
    kind, lang, inner, had_fence = _classify_selection("```mermaid\ngraph TD\nA --> B\n```")
    assert kind == "mermaid"
    assert had_fence is True
    assert "graph TD" in inner


def test_classify_selection_python_inner():
    kind, lang, inner, had_fence = _classify_selection("import numpy as np\nprint(1)")
    assert kind == "code"
    assert lang == "python"
    assert had_fence is False


def test_regenerate_selection_requires_llm(monkeypatch):
    monkeypatch.setattr(
        "backend.transcripts.block_regenerate.ollama_available",
        lambda llm=None: False,
    )
    try:
        regenerate_selection(selection="## Broken heading")
        assert False, "expected RuntimeError"
    except RuntimeError as exc:
        assert "LLM" in str(exc)


def test_regenerate_block_requires_llm(monkeypatch):
    monkeypatch.setattr(
        "backend.transcripts.block_regenerate.ollama_available",
        lambda llm=None: False,
    )
    try:
        regenerate_block(block_type="code", language="python", content="undefined")
        assert False, "expected RuntimeError"
    except RuntimeError as exc:
        assert "LLM" in str(exc)
