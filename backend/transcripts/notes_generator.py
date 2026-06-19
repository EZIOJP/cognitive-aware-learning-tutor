"""Generate markdown lecture notes from cleaned transcripts via Ollama."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path

from backend.core.ollama_client import LlmOptions, ollama_available, ollama_generate
from backend.paths import NOTES_DIR, TRANSCRIPTS_DIR
from backend.transcripts.cleanup import (
    chunk_by_words,
    clean_transcript,
    count_code_blocks,
    count_mermaid_blocks,
    postprocess_markdown,
)
from backend.transcripts.snapshots import inject_snapshot_images

log = logging.getLogger(__name__)

CHUNK_PROMPT = """You are creating lecture study notes from a live-caption transcript chunk.

Rules:
- Output markdown ONLY (no preamble like "Here's your summary").
- Start with a ## heading for the main topic in this chunk.
- Write 3-5 bullet key points (concise lecture notes, not verbatim transcript).
- If a process, flow, or relationship is described, include a ```mermaid diagram (flowchart LR or TD).
- If code or algorithms are discussed, include fenced ``` code blocks.
- Focus on concepts; filler words are already removed.

Transcript chunk:
{chunk}
"""


def summarize_chunk(chunk: str, *, aggressive: bool = False, llm: LlmOptions | None = None) -> str | None:
    if aggressive:
        prompt = (
            "This is a noisy live-caption dump with repeated partial snapshots. "
            "Extract only clean lecture content as markdown notes.\n\n"
            + CHUNK_PROMPT.format(chunk=chunk[:12000])
        )
    else:
        prompt = CHUNK_PROMPT.format(chunk=chunk[:12000])
    return ollama_generate(prompt, timeout=180.0, llm=llm)


def generate_notes_from_text(
    raw: str,
    *,
    title: str = "lecture",
    aggressive: bool = False,
    llm: LlmOptions | None = None,
    folder_path: str = "",
) -> tuple[Path, str]:
    if not ollama_available(llm):
        raise RuntimeError(
            "Local LLM is not enabled. Set OLLAMA_ENABLED=1 in .env, "
            "then start Ollama or LM Studio with your model loaded."
        )

    cleaned = clean_transcript(raw, aggressive=aggressive)
    if not cleaned:
        raise ValueError("Transcript is empty after cleanup.")

    chunks = chunk_by_words(cleaned)
    if not chunks:
        chunks = [cleaned]

    sections: list[str] = [f"# {title.replace('_', ' ')}\n"]
    for i, chunk in enumerate(chunks, start=1):
        log.info("Summarizing chunk %s/%s (%s words)", i, len(chunks), len(chunk.split()))
        section = summarize_chunk(chunk, aggressive=aggressive, llm=llm)
        if not section:
            raise RuntimeError(f"LLM returned empty response for chunk {i}.")
        section = postprocess_markdown(section)
        sections.append(section)

    body = "\n\n".join(sections)
    mermaid_count = count_mermaid_blocks(body)
    code_count = count_code_blocks(body)
    log.info("Notes generated: %s mermaid blocks, %s code blocks", mermaid_count, code_count)

    from backend.transcripts.library import build_relative_path, normalize_folder_path

    NOTES_DIR.mkdir(parents=True, exist_ok=True)
    folder = normalize_folder_path(folder_path)
    if folder:
        (NOTES_DIR / folder).mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    safe_title = "".join(c if c.isalnum() or c in "-_" else "_" for c in title)[:60]
    relative = build_relative_path(folder, f"{safe_title}_{stamp}.md")
    path = NOTES_DIR / relative
    path.write_text(body, encoding="utf-8")
    return path, body


def generate_notes_from_file(
    transcript_path: Path,
    *,
    title: str | None = None,
    aggressive: bool = False,
    llm: LlmOptions | None = None,
    folder_path: str = "",
) -> tuple[Path, str]:
    if not transcript_path.is_file():
        raise FileNotFoundError(f"Transcript not found: {transcript_path}")
    raw = transcript_path.read_text(encoding="utf-8")
    raw = inject_snapshot_images(raw, transcript_path.stem)
    note_title = title or transcript_path.stem
    return generate_notes_from_text(
        raw, title=note_title, aggressive=aggressive, llm=llm, folder_path=folder_path
    )


def resolve_transcript_path(filename: str) -> Path:
    path = TRANSCRIPTS_DIR / filename
    if not path.resolve().is_relative_to(TRANSCRIPTS_DIR.resolve()):
        raise ValueError("Invalid transcript path.")
    return path


def resolve_notes_path(relative_path: str) -> Path:
    rel = relative_path.replace("\\", "/").lstrip("/")
    if ".." in rel.split("/"):
        raise ValueError("Invalid notes path.")
    path = (NOTES_DIR / rel).resolve()
    if not path.is_relative_to(NOTES_DIR.resolve()):
        raise ValueError("Invalid notes path.")
    return path


def list_transcripts() -> list[dict]:
    TRANSCRIPTS_DIR.mkdir(parents=True, exist_ok=True)
    items = []
    for p in sorted(TRANSCRIPTS_DIR.glob("*.txt"), key=lambda x: x.stat().st_mtime, reverse=True):
        items.append({"filename": p.name, "size_bytes": p.stat().st_size, "modified": p.stat().st_mtime})
    return items


def list_notes() -> list[dict]:
    NOTES_DIR.mkdir(parents=True, exist_ok=True)
    items = []
    for p in sorted(NOTES_DIR.rglob("*.md"), key=lambda x: x.stat().st_mtime, reverse=True):
        rel = p.relative_to(NOTES_DIR).as_posix()
        items.append({"filename": rel, "size_bytes": p.stat().st_size, "modified": p.stat().st_mtime})
    return items
