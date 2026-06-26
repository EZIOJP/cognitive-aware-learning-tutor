"""Note content lint helpers."""

from __future__ import annotations

import re

from backend.corpus.code_lint import lint_python_block
from backend.transcripts.mermaid.pipeline import layout_safe_mermaid_source

_MERMAID_FENCE = re.compile(r"```mermaid\s*\n([\s\S]*?)```", re.MULTILINE)
_PYTHON_FENCE = re.compile(r"```python\s*\n([\s\S]*?)```", re.MULTILINE)


def sanitize_note_content(content: str) -> str:
    """Run mermaid + python lint pipeline before persisting notes."""

    def mermaid_repl(match: re.Match[str]) -> str:
        safe = layout_safe_mermaid_source(match.group(1))
        return f"```mermaid\n{safe}\n```"

    out = _MERMAID_FENCE.sub(mermaid_repl, content)

    def python_repl(match: re.Match[str]) -> str:
        code = match.group(1)
        report = lint_python_block(code)
        if report["ok"]:
            return match.group(0)
        return f"```python\n# lint: {'; '.join(report['errors'])}\n{code}\n```"

    return _PYTHON_FENCE.sub(python_repl, out)
