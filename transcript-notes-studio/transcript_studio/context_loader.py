"""Load prerequisite notes, text, and Jupyter notebooks from a context folder."""

from __future__ import annotations

import json
from pathlib import Path

CONTEXT_EXTENSIONS = {".md", ".txt", ".ipynb", ".py", ".json", ".pdf"}
MAX_FILE_CHARS = 80_000
MAX_TOTAL_CHARS = 240_000


def read_text_file(path: Path, *, max_chars: int | None = None) -> str:
    limit = max_chars or MAX_FILE_CHARS
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return ""
    if len(text) > limit:
        text = text[:limit] + "\n\n… [truncated]"
    return text.strip()


def extract_ipynb(path: Path, *, max_chars: int | None = None) -> str:
    limit = max_chars or MAX_FILE_CHARS
    try:
        nb = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return ""
    parts: list[str] = []
    for cell in nb.get("cells") or []:
        ctype = cell.get("cell_type", "")
        source = cell.get("source") or []
        if isinstance(source, list):
            body = "".join(source)
        else:
            body = str(source)
        body = body.strip()
        if not body:
            continue
        if ctype == "markdown":
            parts.append(body)
        elif ctype == "code":
            parts.append(f"```python\n{body}\n```")
    text = "\n\n".join(parts)
    if len(text) > limit:
        text = text[:limit] + "\n\n… [truncated]"
    return text


def load_context_folder(
    folder: str | Path | None,
    *,
    max_total: int | None = None,
    exclude_paths: set[Path] | None = None,
) -> str:
    if not folder:
        return ""
    root = Path(folder).expanduser()
    if not root.is_dir():
        return ""

    excluded = {p.resolve() for p in (exclude_paths or set())}
    cap = max_total or MAX_TOTAL_CHARS
    blocks: list[str] = []
    total = 0
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        if path.suffix.lower() not in CONTEXT_EXTENSIONS:
            continue
        if path.name.startswith("."):
            continue
        if path.resolve() in excluded:
            continue
        rel = path.relative_to(root).as_posix()
        ext = path.suffix.lower()
        if ext == ".ipynb":
            body = extract_ipynb(path)
        elif ext == ".pdf":
            try:
                from transcript_studio.source_loader import _extract_pdf

                body = _extract_pdf(path, max_chars=MAX_FILE_CHARS)
            except (RuntimeError, ValueError):
                continue
        else:
            body = read_text_file(path)
        if not body:
            continue
        block = f"### Context file: {rel}\n\n{body}"
        if total + len(block) > cap:
            remaining = cap - total
            if remaining > 200:
                blocks.append(block[:remaining] + "\n\n… [context truncated]")
            break
        blocks.append(block)
        total += len(block)

    if not blocks:
        return ""
    return "\n\n---\n\n".join(blocks)
