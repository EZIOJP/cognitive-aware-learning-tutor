"""Regenerate a single fenced block (mermaid or code) via local LLM."""

from __future__ import annotations

import re

from backend.core.ollama_client import LlmOptions, ollama_available, ollama_generate
from backend.transcripts.cleanup import sanitize_mermaid_source

_FENCE_RE = re.compile(r"^```(?:\w+)?\s*\n?", re.MULTILINE)
_TRAILING_FENCE_RE = re.compile(r"\n?```\s*$", re.MULTILINE)


def _strip_fences(raw: str) -> str:
    text = raw.strip()
    text = _FENCE_RE.sub("", text, count=1)
    text = _TRAILING_FENCE_RE.sub("", text)
    return text.strip()


def _build_prompt(
    *,
    block_type: str,
    language: str,
    content: str,
    error: str | None,
    instruction: str | None,
    note_context: str | None,
    mode: str = "fix",
) -> str:
    lang = language or block_type
    error_line = f"\nMermaid parse/render error (fix this): {error}" if error else ""
    user_instruction = f"\nUser instruction: {instruction}" if instruction else ""
    context = ""
    if note_context:
        context = f"\n\nSurrounding note context (headings/bullets above and below this block — use for topic only, not syntax):\n---\n{note_context[:3500]}\n---"

    mermaid_rules = """
Mermaid syntax rules (critical):
- One node definition per line; connect with -->
- Edge labels MUST use pipe form: A -->|Yes| B or A -->|No (Blank)| B — never `A -- text --> B`
- Node labels with parentheses, brackets [i], ampersands, or array indexing (arr[i]) MUST use quoted form: id["Process: arr[i]"]
- Never use stadium syntax id(text) — use id["text"] instead
- Never use `F & G --> H`; use two lines: F --> H and G --> H
- Do not use parentheses inside {{}} diamond labels — use id["text"] instead
- Prefer flowchart TD or graph TD"""

    if block_type == "mermaid":
        if mode == "polish":
            return f"""Polish this user-edited Mermaid diagram into perfect, renderable syntax. Return ONLY valid Mermaid — no markdown fences, no explanation.

Rules:
- Preserve the user's structure, nodes, and meaning from their draft
- Fix syntax errors, invalid node IDs, and special characters in labels{mermaid_rules}
- Output must render in standard Mermaid without errors{error_line}{user_instruction}{context}

User-edited Mermaid draft:
{content.strip() or "(empty)"}
"""

        return f"""Fix this broken Mermaid diagram source. Return ONLY valid Mermaid syntax — no markdown fences, no explanation.

Rules:{mermaid_rules}
- Keep the same meaning as the broken source when possible{error_line}{user_instruction}{context}

Broken Mermaid source:
{content.strip() or "(empty)"}
"""

    return f"""Fix this broken {lang} code block from study notes. Return ONLY executable {lang} source — no markdown fences, no explanation, no step labels.

Rules:
- If content is "undefined", empty, or placeholder, infer sensible example code from the note context
- Preserve imports and variable names when fixing
- For Python: use valid syntax, include print() when demonstrating output
- Do not include "Step 1:" style labels inside the code{error_line}{user_instruction}{context}

Broken {lang} source:
{content.strip() or "(empty)"}
"""


def regenerate_block(
    *,
    block_type: str,
    language: str,
    content: str,
    error: str | None = None,
    instruction: str | None = None,
    note_context: str | None = None,
    mode: str = "fix",
    llm: LlmOptions | None = None,
) -> str:
    if not ollama_available(llm):
        raise RuntimeError("LLM is not reachable. Start Ollama/LM Studio or set OLLAMA_ENABLED=1.")

    effective_instruction = instruction
    if block_type == "mermaid" and mode == "polish" and not instruction:
        effective_instruction = None

    prompt = _build_prompt(
        block_type=block_type,
        language=language,
        content=content,
        error=error,
        instruction=effective_instruction,
        note_context=note_context,
        mode=mode,
    )
    raw = ollama_generate(
        prompt,
        timeout=90.0,
        llm=llm,
        system_prompt="You output raw source code or diagram text only. Never wrap in markdown fences.",
    )
    if not raw:
        raise RuntimeError("LLM returned no content.")

    cleaned = _strip_fences(raw)
    if block_type == "mermaid":
        cleaned = cleaned.strip()
        if cleaned.lower().startswith("mermaid"):
            cleaned = cleaned.split("\n", 1)[-1].strip()
        cleaned = sanitize_mermaid_source(cleaned)
    return cleaned.strip()


def _build_selection_prompt(
    *,
    selection: str,
    note_context: str | None,
    instruction: str | None,
) -> str:
    user_instruction = f"\nUser instruction: {instruction}" if instruction else ""
    context = ""
    if note_context:
        context = (
            f"\n\nSurrounding note context (markdown above and below the selection — "
            f"use for topic and tone only; do not copy verbatim into output):\n---\n"
            f"{note_context[:4000]}\n---"
        )

    return f"""Improve this markdown fragment from lecture study notes. Return ONLY the replacement text for the selected region — no preamble, no explanation.

Rules:
- Output must be valid markdown that fits seamlessly between the context above and below
- Preserve the intent of the selection; fix broken syntax, unclear wording, or invalid mermaid/code
- Keep the same structural role (heading level, list, paragraph, fenced block) unless improving clarity requires a small change
- For ```mermaid blocks: one node per line; quote labels with parentheses or arr[i] as id["label"]
- For ```python blocks: return executable code only inside the fence, no "Step 1:" labels
- Do not wrap the entire response in an outer markdown code fence
- Do not repeat headings or bullets from the surrounding context{user_instruction}{context}

Selected markdown to rewrite:
---
{selection.strip() or "(empty)"}
---
"""


def _classify_selection(selection: str) -> tuple[str | None, str, str, bool]:
    """Return (block_type, language, inner_content, had_fence)."""
    stripped = selection.strip()
    fence_match = re.match(r"^```(mermaid|python|py|javascript|js)\s*\n([\s\S]*?)```\s*$", stripped, re.I)
    if fence_match:
        lang = fence_match.group(1).lower()
        inner = fence_match.group(2).strip()
        if lang == "mermaid":
            return "mermaid", "mermaid", inner, True
        code_lang = "python" if lang in ("python", "py") else "javascript"
        return "code", code_lang, inner, True

    if re.match(r"^(graph|flowchart)\s", stripped, re.I):
        return "mermaid", "mermaid", stripped, False

    if re.search(r"^\s*(import |from |def |class |print\()", stripped, re.M):
        return "code", "python", stripped, False

    return None, "", stripped, False


def _wrap_block_output(block_type: str, language: str, inner: str, *, had_fence: bool, original: str) -> str:
    if block_type == "mermaid":
        body = sanitize_mermaid_source(inner)
        if had_fence or "```mermaid" in original.lower():
            return f"```mermaid\n{body}\n```"
        return body
    if had_fence or re.search(r"^```(?:python|py|javascript|js)\s", original, re.I | re.M):
        lang = language or "python"
        return f"```{lang}\n{inner.strip()}\n```"
    return inner.strip()


def regenerate_selection(
    *,
    selection: str,
    note_context: str | None = None,
    instruction: str | None = None,
    llm: LlmOptions | None = None,
) -> str:
    if not selection.strip():
        raise ValueError("Selection is empty.")
    if not ollama_available(llm):
        raise RuntimeError("LLM is not reachable. Start Ollama/LM Studio or set OLLAMA_ENABLED=1.")

    block_type, language, inner, had_fence = _classify_selection(selection)

    if block_type:
        fixed_inner = regenerate_block(
            block_type=block_type,
            language=language,
            content=inner,
            note_context=note_context,
            mode="fix",
            llm=llm,
        )
        return _wrap_block_output(
            block_type,
            language,
            fixed_inner,
            had_fence=had_fence,
            original=selection,
        )

    prompt = _build_selection_prompt(
        selection=selection,
        note_context=note_context,
        instruction=instruction,
    )
    raw = ollama_generate(
        prompt,
        timeout=120.0,
        llm=llm,
        system_prompt="You output raw markdown only. Never add preamble or wrap the whole answer in fences.",
    )
    if not raw:
        raise RuntimeError("LLM returned no content.")

    cleaned = _strip_fences(raw).strip()

    # If selection was a mermaid fence block, sanitize inner diagram
    mermaid_match = re.search(r"```mermaid\s*\n([\s\S]*?)```", cleaned, re.I)
    if mermaid_match:
        inner = sanitize_mermaid_source(mermaid_match.group(1))
        cleaned = re.sub(
            r"```mermaid\s*\n[\s\S]*?```",
            f"```mermaid\n{inner}\n```",
            cleaned,
            count=1,
            flags=re.I,
        )
    elif re.match(r"^(graph|flowchart)\s", cleaned, re.I):
        cleaned = sanitize_mermaid_source(cleaned)

    return cleaned.strip()
