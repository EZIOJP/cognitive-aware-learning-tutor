"""One-off hybrid notes smoke test with mock LLM (proper fenced blocks)."""

from __future__ import annotations

import json
import re
from pathlib import Path
from unittest.mock import patch

from backend.core.log_setup import setup_logging
from backend.core.ollama_client import LlmOptions
from backend.transcripts.hybrid_notes import generate_hybrid_grounded_notes

calls = {"n": 0}


def mock_generate(prompt: str, **kwargs) -> str:
    calls["n"] += 1
    m = re.search(r"Transcript chunk:\s*\n(.*)", prompt, re.S)
    snippet = (m.group(1) if m else prompt)[:80].strip().replace("\n", " ")
    return (
        f"## Chunk {calls['n']}\n\n"
        f"- Topic: {snippet}\n\n"
        "```mermaid\n"
        "flowchart TD\n"
        "  A -- bad legacy --> B\n"
        "```\n\n"
        "```python\n"
        "def broken(:\n"
        "    return 1\n"
        "```\n"
    )


def main() -> None:
    setup_logging()
    llm = LlmOptions(provider="mock", base_url="mock", model="mock")

    def progress(msg: str) -> None:
        print("PROGRESS:", msg)

    with patch("backend.transcripts.notes_generator.ollama_generate", side_effect=mock_generate):
        with patch("backend.transcripts.block_regenerate.ollama_generate", side_effect=mock_generate):
            with patch("backend.transcripts.mermaid.regenerate.ollama_generate", side_effect=mock_generate):
                with patch("backend.core.ollama_client.ollama_available", return_value=True):
            result = generate_hybrid_grounded_notes(
                transcript_file="live_captions_20260613_102757.txt",
                topic="linear algebra smoke",
                title="Smoke Test Notes Lint",
                folder_path="smoke_tests",
                llm=llm,
                ingest_corpus=False,
                on_progress=progress,
                max_chunks=2,
                fast_mode=False,
            )

    md = result.get("markdown") or ""
    path = Path(result["notes_path"])
    lint_lines = [ln for ln in md.splitlines() if "LINT_FAILED" in ln]
    print(
        json.dumps(
            {
                "notes_path": str(path),
                "chunk_count": result.get("chunk_count"),
                "queries": [c.get("query") for c in result.get("chunks", [])],
                "lint_failed_count": len(lint_lines),
                "lint_lines": lint_lines,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
