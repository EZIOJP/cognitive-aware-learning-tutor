"""Generate markdown lecture notes from cleaned transcripts via Ollama."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from backend.core.ollama_client import LlmOptions, ollama_available, ollama_generate
from backend.paths import NOTES_DIR, TRANSCRIPTS_DIR
from backend.transcripts.cleanup import (
    chunk_by_words,
    clean_transcript,
    count_code_blocks,
    count_mermaid_blocks,
    postprocess_markdown,
)
from backend.transcripts.path_utils import build_relative_path, normalize_folder_path
from backend.transcripts.snapshots import append_snapshot_gallery, inject_snapshot_images
from backend.transcripts.semantic_grouper import group_transcript, groups_from_word_chunks
from backend.transcripts.sources import load_context_folder, prepare_sources, reference_slice, resolve_source_path

log = logging.getLogger(__name__)

REFINE_PROMPT = """Polish these lecture notes into one cohesive markdown document.
- Fix duplicate headings and merge overlapping bullets
- Keep mermaid and code blocks intact
- Output markdown only (no preamble)

{body}
"""

GenerateFn = Callable[[str], str | None]


def _resolve_context_folder(context_folder: str) -> Path | None:
    raw = Path(context_folder.strip())
    if raw.is_dir():
        return raw
    candidate = NOTES_DIR / normalize_folder_path(context_folder.strip())
    return candidate if candidate.is_dir() else None


def _merge_reference_materials(existing: str, extra: str) -> str:
    if not extra.strip():
        return existing
    if not existing.strip():
        return extra.strip()
    return f"{existing.strip()}\n\n---\n\n{extra.strip()}"


CHUNK_PROMPT = """You are creating lecture study notes from a live-caption transcript chunk.

Rules:
- Output markdown ONLY (no preamble like "Here's your summary").
- Start with a ## heading for the main topic in this chunk.
- Write 3-5 bullet key points (concise lecture notes, not verbatim transcript).
- If a process, flow, or relationship is described, include a ```mermaid diagram (flowchart TD or LR).
- Mermaid rules: one node per line; use id["label"] when labels contain parentheses, brackets [i], ampersands, or array indexing (e.g. arr[i]); never use stadium id(text & more) syntax.
- Mermaid edge labels MUST use pipe form: A -->|Yes| B — never `A -- text --> B`; never merge edges as `F & G --> H` (use two lines).
- If code or algorithms are discussed, include fenced ``` code blocks.
- Preserve ![Slide N](...) image lines if they appear in the transcript chunk.
- Focus on concepts; filler words are already removed.

Reference material (weave in examples when relevant):
{reference}

Transcript chunk:
{chunk}
"""


def _generate(
    prompt: str,
    *,
    llm: LlmOptions | None,
    generate_fn: GenerateFn | None = None,
    timeout: float = 180.0,
) -> str | None:
    if generate_fn is not None:
        return generate_fn(prompt)
    return ollama_generate(prompt, timeout=timeout, llm=llm)


def summarize_chunk(
    chunk: str,
    *,
    aggressive: bool = False,
    reference_hint: str = "",
    llm: LlmOptions | None = None,
    generate_fn: GenerateFn | None = None,
) -> str | None:
    ref = reference_hint[:6000] if reference_hint.strip() else "(none)"
    body = CHUNK_PROMPT.format(chunk=chunk[:12000], reference=ref)
    if aggressive:
        prompt = (
            "This is a noisy live-caption dump with repeated partial snapshots. "
            "Extract only clean lecture content as markdown notes.\n\n" + body
        )
    else:
        prompt = body
    return _generate(prompt, llm=llm, generate_fn=generate_fn)


def _limit_chunks(chunks: list[str], *, max_chunks: int = 12) -> list[str]:
    """Avoid dozens of sequential LLM calls on long transcripts."""
    if len(chunks) <= max_chunks:
        return chunks
    size = (len(chunks) + max_chunks - 1) // max_chunks
    merged: list[str] = []
    for i in range(0, len(chunks), size):
        merged.append("\n\n".join(chunks[i : i + size]))
    return merged[:max_chunks]


def _select_chunks(
    cleaned: str,
    *,
    use_semantic_grouping: bool = True,
    fast_mode: bool = False,
) -> list[str]:
    if fast_mode:
        chunks = chunk_by_words(cleaned, target_words=5000, overlap_words=100)
        return chunks or [cleaned]

    if use_semantic_grouping:
        groups = group_transcript(cleaned)
        if groups:
            return [g.text for g in groups]
        log.info("Semantic grouping unavailable; using word-chunk fallback")

    chunks = chunk_by_words(cleaned)
    if chunks:
        return chunks
    word_groups = groups_from_word_chunks(cleaned, target_words=2500)
    return [g.text for g in word_groups] if word_groups else [cleaned]


def generate_notes_from_text(
    raw: str,
    *,
    title: str = "lecture",
    aggressive: bool = False,
    llm: LlmOptions | None = None,
    folder_path: str = "",
    output_dir: Path | None = None,
    note_output_path: Path | None = None,
    on_progress: Callable[[str], None] | None = None,
    generate_fn: GenerateFn | None = None,
    already_cleaned: bool = False,
    reference_materials: str = "",
    transcript_stem: str | None = None,
    use_semantic_grouping: bool = True,
    fast_mode: bool = False,
    refine_second_pass: bool = False,
    enrich_with_references: bool = True,
    use_tag_extraction: bool = False,
    context_folder: str | None = None,
    max_chunks: int = 12,
    **kwargs: object,
) -> tuple[Path, str]:
    ctx = (context_folder or "").strip() or str(kwargs.pop("context_folder", "") or "").strip() or None
    if ctx:
        folder = _resolve_context_folder(ctx)
        if folder:
            extra_ref = load_context_folder(folder)
            reference_materials = _merge_reference_materials(reference_materials, extra_ref)

    if generate_fn is None and not ollama_available(llm):
        raise RuntimeError(
            "Local LLM is not enabled. Set OLLAMA_ENABLED=1 in .env, "
            "then start Ollama or LM Studio with your model loaded."
        )

    def progress(msg: str) -> None:
        log.info(msg)
        if on_progress:
            on_progress(msg)

    cleaned = raw if already_cleaned else clean_transcript(raw, aggressive=aggressive)
    if not cleaned:
        raise ValueError("Transcript is empty after cleanup.")

    chunks = _select_chunks(
        cleaned,
        use_semantic_grouping=use_semantic_grouping,
        fast_mode=fast_mode,
    )
    cap = max(4, int(max_chunks))
    if fast_mode:
        cap = min(cap, 8)
    if len(chunks) > cap:
        progress(f"Merging {len(chunks)} chunks → {cap} LLM passes (use --full for more detail)…")
        chunks = _limit_chunks(chunks, max_chunks=cap)

    sections: list[str] = [f"# {title.replace('_', ' ')}\n"]
    total = len(chunks)
    for i, chunk in enumerate(chunks, start=1):
        progress(f"Summarizing chunk {i}/{total} ({len(chunk.split())} words)…")
        ref_hint = reference_materials
        if enrich_with_references and reference_materials.strip() and total > 1:
            ref_hint = reference_slice(reference_materials, i, total)
        section = summarize_chunk(
            chunk,
            aggressive=aggressive,
            reference_hint=ref_hint,
            llm=llm,
            generate_fn=generate_fn,
        )
        if not section:
            raise RuntimeError(f"LLM returned empty response for chunk {i}.")
        section = postprocess_markdown(section)
        if use_tag_extraction:
            from backend.transcripts.tag_engine import (
                TaggedDraft,
                annotate_draft_with_topics,
                extract_tags_for_draft,
            )

            def _tag_generate(prompt: str, _opts: object) -> str | None:
                return _generate(prompt, llm=llm, generate_fn=generate_fn)

            tags = extract_tags_for_draft(section, _tag_generate, None)
            section = annotate_draft_with_topics(TaggedDraft(draft=section, tags=tags))
        sections.append(section)

    body = "\n\n".join(sections)
    if refine_second_pass:
        progress("Refining notes (second pass)…")
        refined = _generate(
            REFINE_PROMPT.format(body=body[:24_000]),
            llm=llm,
            generate_fn=generate_fn,
            timeout=240.0,
        )
        if refined:
            body = postprocess_markdown(refined)
    if transcript_stem:
        body = append_snapshot_gallery(body, transcript_stem)
    progress(
        f"Done — {count_mermaid_blocks(body)} mermaid, {count_code_blocks(body)} code blocks"
    )

    out_root = output_dir or NOTES_DIR
    out_root.mkdir(parents=True, exist_ok=True)
    folder = normalize_folder_path(folder_path)
    if folder:
        (out_root / folder).mkdir(parents=True, exist_ok=True)

    if note_output_path:
        path = note_output_path
    else:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        safe_title = "".join(c if c.isalnum() or c in "-_" else "_" for c in title)[:60].strip()
        safe_title = safe_title.replace(" ", "_") or "lecture"
        relative = build_relative_path(folder, f"{safe_title}_{stamp}.md")
        path = out_root / relative if output_dir else NOTES_DIR / relative

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")
    return path, body


def generate_notes_from_sources(
    source_paths: list[Path],
    *,
    title: str = "lecture",
    aggressive: bool = False,
    llm: LlmOptions | None = None,
    folder_path: str = "",
    on_progress: Callable[[str], None] | None = None,
    **kwargs: object,
) -> tuple[Path, str]:
    if not source_paths:
        raise ValueError("Select at least one source file.")

    transcript_text, reference_text, auto_aggressive, _manifest = prepare_sources(source_paths)
    if auto_aggressive and not aggressive:
        aggressive = True
    stem = source_paths[0].stem if source_paths else None

    extra_ref = str(kwargs.pop("reference_materials", "") or "")
    if reference_text:
        extra_ref = f"{extra_ref}\n\n---\n\n{reference_text}".strip() if extra_ref else reference_text

    return generate_notes_from_text(
        transcript_text,
        title=title,
        aggressive=aggressive,
        llm=llm,
        folder_path=folder_path,
        reference_materials=extra_ref,
        transcript_stem=stem,
        on_progress=on_progress,
        **kwargs,
    )


def generate_notes_from_file(
    transcript_path: Path,
    *,
    title: str | None = None,
    aggressive: bool = False,
    llm: LlmOptions | None = None,
    folder_path: str = "",
    reference_paths: list[Path] | None = None,
    on_progress: Callable[[str], None] | None = None,
    **kwargs: object,
) -> tuple[Path, str]:
    if not transcript_path.is_file():
        raise FileNotFoundError(f"Transcript not found: {transcript_path}")

    note_title = title or transcript_path.stem.replace("_", " ")

    context_folder = kwargs.pop("context_folder", None)
    if context_folder:
        folder = _resolve_context_folder(str(context_folder))
        if folder:
            extra_ref = load_context_folder(folder, exclude_paths={transcript_path.resolve()})
            kwargs["reference_materials"] = _merge_reference_materials(
                str(kwargs.get("reference_materials") or ""),
                extra_ref,
            )

    if reference_paths:
        paths = [transcript_path, *reference_paths]
        return generate_notes_from_sources(
            paths,
            title=note_title,
            aggressive=aggressive,
            llm=llm,
            folder_path=folder_path,
            on_progress=on_progress,
            **kwargs,
        )

    raw = transcript_path.read_text(encoding="utf-8")
    raw = inject_snapshot_images(raw, transcript_path.stem)
    return generate_notes_from_text(
        raw,
        title=note_title,
        aggressive=aggressive,
        llm=llm,
        folder_path=folder_path,
        transcript_stem=transcript_path.stem,
        on_progress=on_progress,
        **kwargs,
    )


def resolve_transcript_path(filename: str) -> Path:
    path = TRANSCRIPTS_DIR / filename
    if not path.resolve().is_relative_to(TRANSCRIPTS_DIR.resolve()):
        raise ValueError("Invalid transcript path.")
    return path


def resolve_notes_path(relative_path: str) -> Path:
    return resolve_source_path(relative_path)


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
