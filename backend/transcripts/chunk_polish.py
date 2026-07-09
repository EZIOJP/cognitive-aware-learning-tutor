"""Per-chunk polish after LLM note generation — mermaid layout-safe + code lint + fences."""

from __future__ import annotations

import logging
from typing import Any, Callable

from backend.core.ollama_client import LlmOptions

log = logging.getLogger(__name__)
from backend.corpus.code_lint import lint_python_block
from backend.transcripts.cleanup import postprocess_markdown
from backend.transcripts.note_document import (
    finalize_note_markdown,
    layout_safe_mermaid_blocks,
    list_fenced_blocks,
    mermaid_still_broken,
    prepare_note_markdown,
)
from backend.transcripts.note_lint import sanitize_note_content


def polish_chunk_text_only(section: str) -> str:
    """Per-chunk polish without mermaid layout — visuals added after full merge."""
    if not (section or "").strip():
        return section
    text = postprocess_markdown(section, sanitize_mermaid=False)
    text = prepare_note_markdown(text)
    return text.strip()


def polish_chunk_after_generation(section: str) -> str:
    """
    Run after each LLM chunk before append:
    1. Strip preamble / repair fences (postprocess)
    2. Step-code + mermaid fence repair (prepare)
    3. Mermaid layout-safe sanitize
    4. Python lint annotations on bad blocks
    """
    if not (section or "").strip():
        return section
    text = postprocess_markdown(section)
    text = prepare_note_markdown(text)
    text = layout_safe_mermaid_blocks(text)
    text = sanitize_note_content(text)
    return text.strip()


def _lint_failures(markdown: str) -> list[dict[str, Any]]:
    failures: list[dict[str, Any]] = []
    for block in list_fenced_blocks(markdown):
        if block.lang == "mermaid" and mermaid_still_broken(block.content):
            failures.append(
                {
                    "index": block.index,
                    "lang": block.lang,
                    "reason": "mermaid syntax still broken after sanitize",
                }
            )
            continue
        if block.lang in {"python", "py"}:
            report = lint_python_block(block.content)
            if not report.get("ok"):
                failures.append(
                    {
                        "index": block.index,
                        "lang": block.lang,
                        "reason": "; ".join(report.get("errors", [])) or "python lint failed",
                    }
                )
    return failures


def _annotate_lint_failures(markdown: str, failures: list[dict[str, Any]]) -> str:
    if not failures:
        return markdown
    comments = [
        f"<!-- LINT_FAILED: block {f['index']} ({f['lang']}) {f['reason']} -->"
        for f in failures
    ]
    return markdown.rstrip() + "\n\n" + "\n".join(comments) + "\n"


def finalize_full_note(
    body: str,
    *,
    repair_blocks: bool = True,
    use_llm_repair: bool = False,
    enrich_visuals: bool = True,
    llm: LlmOptions | None = None,
    on_progress: Callable[[str], None] | None = None,
) -> str:
    """
    Final pass on merged document before write.
    Local block repair by default; LLM repair optional (slow).
    """
    from backend.transcripts.note_block_repair import repair_all_blocks

    text = prepare_note_markdown(body)
    if enrich_visuals:
        from backend.transcripts.note_enrich import enrich_note_with_visuals

        text = enrich_note_with_visuals(text, llm=llm, on_progress=on_progress)
        text = prepare_note_markdown(text)
    if repair_blocks:
        text, _details = repair_all_blocks(text, llm=llm, use_llm=use_llm_repair)
    text = finalize_note_markdown(text)

    failures = _lint_failures(text)
    if not failures:
        return text

    # Hard gate: one retry with LLM-assisted block repair, then save with visible warning comments.
    try:
        repaired, _retry_details = repair_all_blocks(text, llm=llm, use_llm=True)
        repaired = finalize_note_markdown(repaired)
        remaining = _lint_failures(repaired)
        if not remaining:
            return repaired
        log.warning("Lint gate: %d block(s) still broken after LLM retry", len(remaining))
        return _annotate_lint_failures(repaired, remaining)
    except Exception as exc:  # noqa: BLE001
        log.warning("Lint gate LLM retry failed (%s) — saving with LINT_FAILED markers", exc)
        return _annotate_lint_failures(text, failures)
