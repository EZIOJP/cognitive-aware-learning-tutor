"""Study Library intelligence — gap analysis, quiz/drill generation, session sync."""

from __future__ import annotations

import json
import re
import uuid
from typing import Any, Literal

from sqlalchemy.orm import Session

from backend.core.ollama_client import LlmOptions, ollama_available, ollama_generate
from backend.models.study import LectureNote
from backend.transcripts.library import create_note_file, list_notes_in_folder, note_storage_path
from backend.transcripts.notes_generator import resolve_notes_path

_JSON_BLOCK = re.compile(r"\{[\s\S]*\}")

GapSeverity = Literal["high", "medium", "low"]


def _parse_json_blob(text: str) -> dict[str, Any]:
    text = (text or "").strip()
    if text.startswith("{"):
        return json.loads(text)
    match = _JSON_BLOCK.search(text)
    if match:
        return json.loads(match.group())
    raise ValueError("No JSON object in LLM response")


def load_note_text(db: Session, user_id: int, relative_path: str, *, max_chars: int = 24_000) -> str:
    rel = relative_path.replace("\\", "/").strip()
    if not rel or ".." in rel:
        raise ValueError("Invalid note path.")

    path = resolve_notes_path(rel)
    if not path.is_file():
        raise FileNotFoundError("Note file not found on disk.")

    text = path.read_text(encoding="utf-8")
    if len(text) > max_chars:
        text = text[:max_chars] + "\n\n… [truncated for analysis]"
    return text


def _clip(s: str, n: int = 400) -> str:
    s = (s or "").strip()
    return s if len(s) <= n else s[: n - 1] + "…"


def _citation_for_chunk(chunk_id: str, hits: list[dict[str, Any]]) -> str:
    if not chunk_id:
        return ""
    for h in hits:
        if h.get("chunk_id") == chunk_id:
            return str(h.get("citation") or "")
    return ""


def _corpus_hits_for_topic(
    topic: str,
    *,
    max_chars: int = 12000,
    boost_concepts: list[str] | None = None,
) -> list[dict[str, Any]]:
    """Retrieve grounded chunks when corpus is populated."""
    try:
        from backend.corpus.retrieve import corpus_available, hybrid_retrieve

        if not corpus_available():
            return []
        query = (topic or "study material").strip()[:300]
        if boost_concepts:
            query = f"{query} {' '.join(boost_concepts[:6])}"
        return hybrid_retrieve(query, top_k=5)
    except Exception:  # noqa: BLE001
        return []


def _corpus_material_for_topic(
    topic: str,
    *,
    max_chars: int = 12000,
    boost_concepts: list[str] | None = None,
) -> str | None:
    from backend.corpus.retrieve import format_hits_for_prompt

    hits = _corpus_hits_for_topic(topic, max_chars=max_chars, boost_concepts=boost_concepts)
    if not hits:
        return None
    return format_hits_for_prompt(hits, max_chars=max_chars)


def _combined_source_material(
    source_texts: list[str],
    *,
    topic: str = "",
    max_chars: int = 16000,
    boost_concepts: list[str] | None = None,
) -> tuple[str, list[dict[str, Any]]]:
    hits = _corpus_hits_for_topic(topic, max_chars=max_chars, boost_concepts=boost_concepts)
    if hits:
        from backend.corpus.retrieve import format_hits_for_prompt

        return format_hits_for_prompt(hits, max_chars=max_chars), hits
    joined = "\n\n---\n\n".join(source_texts)[:max_chars]
    return joined, []


def _template_gap_analysis(lecture: str, reference: str) -> dict[str, Any]:
    lecture_lines = [ln.strip() for ln in lecture.splitlines() if ln.strip()][:8]
    ref_lines = [ln.strip() for ln in reference.splitlines() if ln.strip()][:8]
    return {
        "summary": "Template gap scan (enable local LLM for deeper analysis). Compare headings and key terms between your notes and reference.",
        "gaps": [
            {
                "topic": "Coverage check",
                "lecture_excerpt": _clip(lecture_lines[0] if lecture_lines else lecture[:200]),
                "reference_excerpt": _clip(ref_lines[0] if ref_lines else reference[:200]),
                "severity": "medium",
                "suggestion": "Read the reference section and add missing definitions to your lecture notes.",
            }
        ],
        "aligned_topics": [],
        "source": "template",
    }


def run_gap_analysis(
    lecture_text: str,
    reference_text: str,
    *,
    llm: LlmOptions | None = None,
) -> dict[str, Any]:
    if not ollama_available(llm):
        return _template_gap_analysis(lecture_text, reference_text)

    prompt = f"""Compare these two study documents. The first is student lecture notes; the second is reference material (textbook/slides).

Return JSON only with keys:
- summary (string, 2-3 sentences)
- gaps (array of objects with: topic, lecture_excerpt, reference_excerpt, severity ["high"|"medium"|"low"], suggestion)
- aligned_topics (array of strings — topics both cover well)

Limit gaps to at most 8 items. Use short excerpts (under 120 chars each).

LECTURE NOTES:
{lecture_text[:14000]}

REFERENCE:
{reference_text[:14000]}"""

    raw = ollama_generate(prompt, timeout=120.0, llm=llm)
    if not raw:
        return _template_gap_analysis(lecture_text, reference_text)

    parsed = _parse_json_blob(raw)
    gaps = parsed.get("gaps") or []
    clean_gaps = []
    for g in gaps[:8]:
        if not isinstance(g, dict):
            continue
        clean_gaps.append(
            {
                "topic": _clip(str(g.get("topic", "Gap")), 80),
                "lecture_excerpt": _clip(str(g.get("lecture_excerpt", "")), 160),
                "reference_excerpt": _clip(str(g.get("reference_excerpt", "")), 160),
                "severity": g.get("severity") if g.get("severity") in ("high", "medium", "low") else "medium",
                "suggestion": _clip(str(g.get("suggestion", "")), 240),
            }
        )
    return {
        "summary": _clip(str(parsed.get("summary", "")), 600),
        "gaps": clean_gaps or _template_gap_analysis(lecture_text, reference_text)["gaps"],
        "aligned_topics": [str(t)[:80] for t in (parsed.get("aligned_topics") or [])[:12]],
        "source": "gemma",
        "gap_ingest_triggered": _trigger_gap_ingest(clean_gaps),
    }


def _trigger_gap_ingest(gaps: list[dict[str, Any]]) -> list[str]:
    try:
        from backend.corpus.gap_ingest import trigger_gap_ingest_for_gaps

        return trigger_gap_ingest_for_gaps(gaps)
    except Exception:  # noqa: BLE001
        return []


def _template_quiz(sources: list[str], count: int) -> dict[str, Any]:
    title_hint = sources[0][:60] if sources else "Study topic"
    questions = []
    for i in range(min(count, 5)):
        questions.append(
            {
                "id": f"q{i + 1}",
                "question": f"Sample question {i + 1} about {title_hint} (enable LLM for real MCQs).",
                "options": ["Option A", "Option B", "Option C", "Option D"],
                "answer_index": 0,
                "explanation": "Replace by generating with LM Studio / Ollama enabled.",
            }
        )
    return {"questions": questions, "source": "template"}


def generate_quiz_items(
    source_texts: list[str],
    *,
    count: int = 5,
    topic: str = "",
    llm: LlmOptions | None = None,
    boost_concepts: list[str] | None = None,
) -> dict[str, Any]:
    combined, source_hits = _combined_source_material(
        source_texts,
        topic=topic,
        max_chars=16000,
        boost_concepts=boost_concepts,
    )
    allowed_ids = {h["chunk_id"] for h in source_hits}
    n = max(1, min(count, 10))

    if not ollama_available(llm):
        return _template_quiz(source_texts, n)

    prompt = f"""Create {n} multiple-choice study questions from the material below.
Topic focus: {topic or "general"}

Each question MUST cite a source chunk_id from the material headers (<!-- cite: uuid -->).
Return JSON only:
{{"questions": [{{"id": "q1", "question": "...", "options": ["A","B","C","D"], "answer_index": 0, "explanation": "...", "source_chunk_id": "uuid"}}]}}

Material:
{combined}"""

    raw = ollama_generate(prompt, timeout=120.0, llm=llm)
    if not raw:
        return _template_quiz(source_texts, n)

    parsed = _parse_json_blob(raw)
    questions = []
    for i, q in enumerate(parsed.get("questions") or []):
        if not isinstance(q, dict):
            continue
        opts = q.get("options") or []
        if len(opts) < 2:
            continue
        ans = int(q.get("answer_index", 0))
        if ans < 0 or ans >= len(opts):
            ans = 0
        questions.append(
            {
                "id": str(q.get("id") or f"q{i + 1}"),
                "question": _clip(str(q.get("question", "")), 300),
                "options": [_clip(str(o), 120) for o in opts[:6]],
                "answer_index": ans,
                "explanation": _clip(str(q.get("explanation", "")), 300),
                "source_chunk_id": str(q.get("source_chunk_id") or ""),
                "citation": _citation_for_chunk(str(q.get("source_chunk_id") or ""), source_hits),
            }
        )
        if len(questions) >= n:
            break

    if not questions:
        return _template_quiz(source_texts, n)
    try:
        from backend.corpus.citation_check import verify_quiz_citations

        verify_quiz_citations(questions, allowed_ids)
    except Exception:  # noqa: BLE001
        pass
    return {"questions": questions, "source": "gemma"}


def _template_drills(source_texts: list[str], count: int) -> dict[str, Any]:
    drills = []
    for i in range(min(count, 3)):
        drills.append(
            {
                "id": f"d{i + 1}",
                "title": f"Exercise {i + 1}",
                "language": "python",
                "prompt": "Write a short function using concepts from your notes (enable LLM for tailored drills).",
                "starter_code": "# your code here\n",
                "hint": "Review the numpy/array sections in your notes.",
            }
        )
    return {"drills": drills, "source": "template"}


def generate_code_drills(
    source_texts: list[str],
    *,
    count: int = 2,
    topic: str = "",
    llm: LlmOptions | None = None,
    boost_concepts: list[str] | None = None,
) -> dict[str, Any]:
    combined, source_hits = _combined_source_material(
        source_texts,
        topic=topic,
        max_chars=16000,
        boost_concepts=boost_concepts,
    )
    allowed_ids = {h["chunk_id"] for h in source_hits}
    n = max(1, min(count, 5))

    if not ollama_available(llm):
        return _template_drills(source_texts, n)

    prompt = f"""Create {n} coding practice exercises from the study material.
Topic: {topic or "programming concepts from notes"}

Each drill MUST include source_chunk_id from material (<!-- cite: uuid -->).
Return JSON only:
{{"drills": [{{"id": "d1", "title": "...", "language": "python", "prompt": "...", "starter_code": "...", "hint": "...", "source_chunk_id": "uuid"}}]}}

Material:
{combined}"""

    raw = ollama_generate(prompt, timeout=120.0, llm=llm)
    if not raw:
        return _template_drills(source_texts, n)

    parsed = _parse_json_blob(raw)
    drills = []
    for i, d in enumerate(parsed.get("drills") or []):
        if not isinstance(d, dict):
            continue
        drills.append(
            {
                "id": str(d.get("id") or f"d{i + 1}"),
                "title": _clip(str(d.get("title", f"Drill {i + 1}")), 80),
                "language": _clip(str(d.get("language", "python")), 20),
                "prompt": _clip(str(d.get("prompt", "")), 400),
                "starter_code": str(d.get("starter_code", "# starter\n"))[:800],
                "hint": _clip(str(d.get("hint", "")), 200),
                "source_chunk_id": str(d.get("source_chunk_id") or ""),
                "citation": _citation_for_chunk(str(d.get("source_chunk_id") or ""), source_hits),
            }
        )
        if len(drills) >= n:
            break

    if not drills:
        return _template_drills(source_texts, n)
    try:
        from backend.corpus.citation_check import verify_quiz_citations

        verify_quiz_citations(drills, allowed_ids)
    except Exception:  # noqa: BLE001
        pass
    return {"drills": drills, "source": "gemma"}


def quiz_to_markdown(questions: list[dict[str, Any]], *, title: str = "Generated Quiz") -> str:
    lines = [f"# {title}", ""]
    for i, q in enumerate(questions, start=1):
        lines.append(f"## Q{i}. {q.get('question', '')}")
        lines.append("")
        for j, opt in enumerate(q.get("options") or []):
            letter = chr(65 + j)
            lines.append(f"- **{letter}.** {opt}")
        ans = int(q.get("answer_index", 0))
        opts = q.get("options") or []
        answer = opts[ans] if 0 <= ans < len(opts) else ""
        lines.append("")
        lines.append(f"**Answer:** {answer}")
        if q.get("explanation"):
            lines.append("")
            lines.append(f"*{q['explanation']}*")
        lines.append("")
    return "\n".join(lines).strip() + "\n"


def drills_to_markdown(drills: list[dict[str, Any]], *, title: str = "Code Drills") -> str:
    lines = [f"# {title}", ""]
    for i, d in enumerate(drills, start=1):
        lang = d.get("language") or "python"
        lines.append(f"## {i}. {d.get('title', 'Exercise')}")
        lines.append("")
        lines.append(str(d.get("prompt", "")))
        lines.append("")
        if d.get("hint"):
            lines.append(f"*Hint: {d['hint']}*")
            lines.append("")
        lines.append(f"```{lang}")
        lines.append(str(d.get("starter_code", "")).rstrip())
        lines.append("```")
        lines.append("")
    return "\n".join(lines).strip() + "\n"


def gap_summary_markdown(
    gap_result: dict[str, Any],
    *,
    lecture_title: str,
    reference_title: str,
) -> str:
    lines = [
        f"# Gap Analysis: {lecture_title} vs {reference_title}",
        "",
        gap_result.get("summary", ""),
        "",
        "## Gaps",
        "",
    ]
    for g in gap_result.get("gaps") or []:
        lines.append(f"### {g.get('topic', 'Gap')} ({g.get('severity', 'medium')})")
        lines.append("")
        if g.get("lecture_excerpt"):
            lines.append(f"- **Notes:** {g['lecture_excerpt']}")
        if g.get("reference_excerpt"):
            lines.append(f"- **Reference:** {g['reference_excerpt']}")
        if g.get("suggestion"):
            lines.append(f"- **Action:** {g['suggestion']}")
        lines.append("")
    aligned = gap_result.get("aligned_topics") or []
    if aligned:
        lines.append("## Aligned topics")
        lines.append("")
        for t in aligned:
            lines.append(f"- {t}")
        lines.append("")
    return "\n".join(lines).strip() + "\n"


def sync_session_items(
    db: Session,
    *,
    user_id: int,
    folder_path: str,
    items: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    saved: list[dict[str, Any]] = []
    for item in items:
        if not item.get("approved"):
            continue
        kind = item.get("kind") or "note"
        if kind not in ("quiz", "exercise", "note", "lecture"):
            kind = "note"
        title = str(item.get("title") or "Untitled").strip() or "Untitled"
        content = str(item.get("content") or "")
        if not content.strip():
            continue
        row = create_note_file(
            db,
            user_id=user_id,
            title=title,
            folder_path=folder_path,
            kind=kind,
            content=content,
            topic=item.get("topic"),
        )
        saved.append(
            {
                "id": item.get("id") or str(uuid.uuid4()),
                "relative_path": note_storage_path(row),
                "title": row.title,
                "kind": row.kind,
            }
        )
    return saved


def _template_folder_summary(folder_name: str, parts: list[str]) -> str:
    lines = [
        f"# Folder Summary — {folder_name}",
        "",
        "Template synthesis (enable local LLM for a smarter cross-note summary).",
        "",
        "## Sources",
        "",
    ]
    for block in parts[:8]:
        first = block.split("\n", 1)[0].replace("### Source: ", "")
        lines.append(f"- {first}")
    lines.extend(
        [
            "",
            "## Suggested next steps",
            "",
            "- Skim each source note and merge duplicate definitions.",
            "- Add one consolidated outline section to this summary.",
            "- Flag topics that appear in only one note for review.",
            "",
        ]
    )
    return "\n".join(lines)


def summarize_folder(
    db: Session,
    *,
    user_id: int,
    folder_path: str,
    llm: LlmOptions | None = None,
    title: str | None = None,
) -> dict[str, Any]:
    folder = folder_path.replace("\\", "/").strip()
    paths = list_notes_in_folder(folder, recursive=True)
    if not paths:
        raise ValueError("No notes in this folder.")

    parts: list[str] = []
    for rel in paths[:12]:
        try:
            text = load_note_text(db, user_id, rel, max_chars=6000)
        except (FileNotFoundError, ValueError):
            continue
        name = rel.split("/")[-1].replace(".md", "").replace("_", " ")
        parts.append(f"### Source: {name}\n\n{text}")

    if not parts:
        raise ValueError("Could not read any notes in this folder.")

    combined = "\n\n---\n\n".join(parts)
    folder_name = folder.split("/")[-1] if folder else "Library"

    if ollama_available(llm):
        prompt = f"""Synthesize these study notes from folder "{folder_name}" into ONE smart folder-level summary.

Requirements:
- Cross-note themes and how ideas connect (not a file-by-file recap)
- Consolidated outline with ## headings
- Deduplicated key definitions, formulas, and takeaways
- Gaps, open questions, and a suggested study sequence
- Markdown only (no JSON). Use mermaid only if it clearly helps.

Notes:
{combined[:40_000]}
"""
        md_raw = ollama_generate(prompt, llm=llm)
        if md_raw:
            md = md_raw.strip()
            if not md.startswith("#"):
                md = f"# Folder Summary — {folder_name}\n\n{md}"
        else:
            md = _template_folder_summary(folder_name, parts)
    else:
        md = _template_folder_summary(folder_name, parts)

    out_title = (title or f"Folder Summary — {folder_name}").strip()
    row = create_note_file(
        db,
        user_id=user_id,
        title=out_title,
        folder_path=folder,
        kind="note",
        content=md + "\n",
        topic=folder_name,
    )
    return {
        "relative_path": note_storage_path(row),
        "title": row.title,
        "markdown": md,
        "source_count": len(paths),
        "source": "llm" if ollama_available(llm) else "template",
    }
