"""Smart quiz import: multi-format parse + topic tag resolution for SRS."""

from __future__ import annotations

import json
import re
from typing import Any

from backend.transcripts.note_topics import (
    canonical_library_path,
    normalize_topic_shorthand,
    parse_note_topics,
    parse_topic_index,
)

_LID_RE = re.compile(r"`?(L\s*(\d+)\s*[-_]\s*T\s*(\d+))`?", re.IGNORECASE)
_TAG_LINE_RE = re.compile(
    r"(?i)^\s*(?:tags?|topic(?:_id)?|concept|label)\s*[:=]\s*(.+)$",
)
_ANSWER_RE = re.compile(
    r"(?i)(?:answer|correct|solution)\s*[:\-=]\s*([A-D]|\d+)",
)
_LETTER_OPTION_RE = re.compile(r"(?m)^\s*([A-Da-d])\s*[\).\:\-]\s*(.+?)\s*$")
_NUM_OPTION_RE = re.compile(r"(?m)^\s*(\d+)\s*[\).\:\-]\s*(.+?)\s*$")
_QUESTION_HEADER_RE = re.compile(r"(?i)(?:^|\n)\s*(?:question\s*)?#?\s*(\d+)\s*[\.:\)]?\s*")


def _clip(text: str, n: int) -> str:
    s = (text or "").strip()
    return s if len(s) <= n else s[: n - 1] + "…"


def canonicalize_topic_id(raw: str) -> str | None:
    """Normalize L5-T5 / l2-t07 → L5-T05 / L2-T07."""
    text = (raw or "").strip().strip("`")
    if not text:
        return None
    m = re.fullmatch(r"L\s*(\d+)\s*[-_]\s*T\s*(\d+)", text, re.IGNORECASE)
    if m:
        return f"L{int(m.group(1))}-T{int(m.group(2)):02d}"
    return normalize_topic_shorthand(text)


def extract_topic_ids_from_text(text: str) -> list[str]:
    """Pull all L{n}-Txx IDs from a metadata line or tag string."""
    found: list[str] = []
    for m in _LID_RE.finditer(text or ""):
        tid = canonicalize_topic_id(m.group(1))
        if tid and tid not in found:
            found.append(tid)
    return found


def _parse_answer_index(block: str, option_count: int) -> int:
    if option_count < 1:
        return 0
    m = _ANSWER_RE.search(block)
    if not m:
        return 0
    token = m.group(1).strip()
    if token.isdigit():
        idx = int(token) - 1
        return max(0, min(idx, option_count - 1))
    return max(0, min(ord(token.upper()) - ord("A"), option_count - 1))


def _normalize_question_dict(raw: dict[str, Any], *, fallback_id: str) -> dict[str, Any] | None:
    question = str(
        raw.get("question")
        or raw.get("prompt")
        or raw.get("stem")
        or raw.get("text")
        or ""
    ).strip()
    options = raw.get("options") or raw.get("choices") or raw.get("answers") or []
    if isinstance(options, str):
        options = [o.strip() for o in re.split(r"[|;/]", options) if o.strip()]
    options = [str(o).strip() for o in options if str(o).strip()]
    if len(question) < 4 or len(options) < 2:
        return None

    answer_index = raw.get("answer_index")
    if answer_index is None and raw.get("answer") is not None:
        ans = raw.get("answer")
        if isinstance(ans, int):
            answer_index = ans
        elif isinstance(ans, str) and ans.strip().isdigit():
            answer_index = int(ans.strip())
        elif isinstance(ans, str) and len(ans.strip()) == 1:
            answer_index = ord(ans.strip().upper()) - ord("A")
    if answer_index is None:
        answer_index = _parse_answer_index(json.dumps(raw), len(options))
    try:
        answer_index = int(answer_index)
    except (TypeError, ValueError):
        answer_index = 0
    answer_index = max(0, min(answer_index, len(options) - 1))

    tags: list[str] = []
    for key in ("tags", "tag", "labels"):
        val = raw.get(key)
        if isinstance(val, str):
            tags.extend([t.strip() for t in re.split(r"[,;|]", val) if t.strip()])
        elif isinstance(val, list):
            tags.extend([str(t).strip() for t in val if str(t).strip()])

    topic_from_field = extract_topic_ids_from_text(str(raw.get("topic") or ""))
    topic_id = canonicalize_topic_id(str(raw.get("topic_id") or raw.get("topicId") or "")) or (
        topic_from_field[0] if topic_from_field else None
    )
    for tid in extract_topic_ids_from_text(" ".join(tags)):
        if not topic_id:
            topic_id = tid
        elif tid not in tags:
            tags.append(tid)

    concept = str(raw.get("concept") or raw.get("label") or raw.get("category") or "").strip()
    if topic_id and not concept:
        concept = topic_id

    return {
        "id": str(raw.get("id") or fallback_id),
        "question": _clip(question, 420),
        "options": [_clip(o, 160) for o in options[:6]],
        "answer_index": answer_index,
        "explanation": _clip(str(raw.get("explanation") or raw.get("rationale") or ""), 500),
        "hint": _clip(str(raw.get("hint") or ""), 200),
        "concept": concept or "Imported",
        "topic_id": topic_id or "",
        "tags": tags,
        "source_chunk_id": str(raw.get("source_chunk_id") or ""),
        "citation": str(raw.get("citation") or "imported"),
        "note_path": str(raw.get("note_path") or raw.get("notePath") or "").replace("\\", "/"),
        "reading_excerpt": _clip(str(raw.get("reading_excerpt") or raw.get("excerpt") or ""), 800),
    }


def _try_parse_json(text: str) -> list[dict[str, Any]] | None:
    blob = text.strip()
    if not blob:
        return None
    fence = re.search(r"```(?:json)?\s*([\s\S]*?)```", blob, re.IGNORECASE)
    if fence:
        blob = fence.group(1).strip()
    try:
        data = json.loads(blob)
    except json.JSONDecodeError:
        return None
    if isinstance(data, dict):
        if isinstance(data.get("questions"), list):
            data = data["questions"]
        elif isinstance(data.get("items"), list):
            data = data["items"]
        else:
            return None
    if not isinstance(data, list):
        return None
    out: list[dict[str, Any]] = []
    for i, row in enumerate(data):
        if not isinstance(row, dict):
            continue
        q = _normalize_question_dict(row, fallback_id=f"import-json-{i + 1}")
        if q:
            out.append(q)
    return out or None


def _try_parse_jsonl(text: str) -> list[dict[str, Any]] | None:
    lines = [ln.strip() for ln in text.splitlines() if ln.strip() and not ln.strip().startswith("#")]
    if len(lines) < 2:
        return None
    if not all(ln.startswith("{") for ln in lines[:3]):
        return None
    out: list[dict[str, Any]] = []
    for i, ln in enumerate(lines):
        try:
            row = json.loads(ln)
        except json.JSONDecodeError:
            return None
        if not isinstance(row, dict):
            return None
        q = _normalize_question_dict(row, fallback_id=f"import-jsonl-{i + 1}")
        if q:
            out.append(q)
    return out or None


def _parse_metadata_prefix(block: str) -> tuple[dict[str, Any], str]:
    """Parse tag/topic lines anywhere in block; return metadata + body with those lines removed."""
    meta: dict[str, Any] = {"tags": []}
    body_lines: list[str] = []
    for ln in block.replace("\r\n", "\n").splitlines():
        stripped = ln.strip()
        if not stripped:
            body_lines.append(ln)
            continue
        if stripped == "---":
            continue
        tag_m = _TAG_LINE_RE.match(stripped)
        if tag_m:
            val = tag_m.group(1).strip()
            tids = extract_topic_ids_from_text(val)
            if tids and not meta.get("topic_id"):
                meta["topic_id"] = tids[0]
            for tid in tids:
                if tid not in meta["tags"]:
                    meta["tags"].append(tid)
            for part in re.split(r"[,;|]", val):
                p = part.strip()
                if p and p not in meta["tags"] and not _LID_RE.search(p):
                    meta["tags"].append(p)
            continue
        inline_ids = extract_topic_ids_from_text(stripped)
        if inline_ids and re.fullmatch(r"[\[\]`@L\d\-Tt\s,;]+", stripped, re.IGNORECASE):
            if not meta.get("topic_id"):
                meta["topic_id"] = inline_ids[0]
            for tid in inline_ids:
                if tid not in meta["tags"]:
                    meta["tags"].append(tid)
            continue
        body_lines.append(ln.rstrip())
    remainder = "\n".join(body_lines).strip()
    return meta, remainder


def _parse_mcq_block(
    block: str,
    *,
    block_index: int,
    section_meta: dict[str, Any] | None = None,
) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    """Parse one MCQ block. Returns (question or None, metadata found in the block)."""
    meta, body = _parse_metadata_prefix(block)
    if section_meta:
        own_topic = bool(meta.get("topic_id"))
        if not own_topic and section_meta.get("topic_id"):
            meta["topic_id"] = section_meta["topic_id"]
        for tag in section_meta.get("tags") or []:
            # Never mix a section topic ID into a question that declares its own.
            if own_topic and _LID_RE.search(tag):
                continue
            if tag not in meta["tags"]:
                meta["tags"].append(tag)
    letter_matches = list(_LETTER_OPTION_RE.finditer(body))
    num_matches = list(_NUM_OPTION_RE.finditer(body)) if len(letter_matches) < 2 else []
    option_matches = letter_matches if len(letter_matches) >= 2 else num_matches
    if len(option_matches) < 2:
        return None, meta

    first_opt_line = option_matches[0].group(0)
    prompt = body.split(first_opt_line, 1)[0].strip()
    prompt = re.sub(r"(?i)^question\s*#?\s*\d+\s*[\.:\)]?\s*", "", prompt).strip()
    prompt = re.sub(r"(?i)^question\s*:?\s*", "", prompt).strip()
    if len(prompt) < 8:
        return None, meta

    options = [m.group(2).strip() for m in option_matches[:6]]
    answer_index = _parse_answer_index(body, len(options))

    concept = ""
    low_p = prompt.casefold()
    if "numpy" in low_p or "np." in low_p:
        concept = "NumPy"
    elif "pandas" in low_p or "dataframe" in low_p or "df." in low_p:
        concept = "Pandas"

    topic_id = meta.get("topic_id") or ""
    tags = list(meta.get("tags") or [])
    for tid in extract_topic_ids_from_text(prompt):
        if not topic_id:
            topic_id = tid
        elif tid not in tags:
            tags.append(tid)

    question = {
        "id": f"import-{block_index + 1}",
        "question": _clip(prompt, 420),
        "options": [_clip(o, 160) for o in options],
        "answer_index": answer_index,
        "explanation": "",
        "hint": f"Review topic: {topic_id or concept}" if (topic_id or concept) else "Review this imported question",
        "concept": concept or (topic_id if topic_id else "Imported"),
        "topic_id": topic_id,
        "tags": tags,
        "source_chunk_id": "",
        "citation": "imported",
    }
    return question, meta


def parse_smart_quiz_import(text: str) -> list[dict[str, Any]]:
    """
    Parse pasted/imported quiz content.

    Supports:
    - JSON array or `{ "questions": [...] }`
    - JSONL (one question object per line)
    - GeeksforGeeks-style blocks with optional tag preamble
    - Per-question metadata: `topic_id: L2-T07`, `Tags: numpy, L2-T08`

    Tags in a header (before the first question) or in a tag-only block cascade to
    every following question until another tag overrides them.
    """
    blob = (text or "").replace("\r\n", "\n").strip()
    if not blob:
        return []

    for parser in (_try_parse_json, _try_parse_jsonl):
        parsed = parser(blob)
        if parsed:
            return parsed

    # Split on Question N headers or --- between items
    parts = _QUESTION_HEADER_RE.split(blob)
    blocks: list[str] = []
    section_meta: dict[str, Any] = {"tags": []}
    if len(parts) > 2:
        section_meta, _ = _parse_metadata_prefix(parts[0])
        for i in range(2, len(parts), 2):
            blocks.append(parts[i].strip())
    else:
        blocks = [b.strip() for b in re.split(r"\n---+\n", blob) if b.strip()]

    if len(blocks) == 1 and "question" not in blocks[0].casefold()[:40]:
        blocks = [blob]

    questions: list[dict[str, Any]] = []
    for bi, block in enumerate(blocks):
        if not block.strip():
            continue
        cleaned_lines: list[str] = []
        for ln in block.splitlines():
            low = ln.casefold().strip()
            if low in {"discuss", "comments"} or low.startswith("last updated"):
                continue
            cleaned_lines.append(ln.rstrip())
        q, block_meta = _parse_mcq_block(
            "\n".join(cleaned_lines),
            block_index=bi,
            section_meta=section_meta,
        )
        if q:
            questions.append(q)
        elif block_meta.get("topic_id") or block_meta.get("tags"):
            # Tag-only block: becomes the default for the questions that follow.
            section_meta = block_meta
    return questions


def build_topic_resolver(note_text: str) -> dict[str, Any]:
    """Index for resolving tags/titles → canonical topic_id."""
    index_titles = parse_topic_index(note_text or "")
    topics = parse_note_topics(note_text or "", min_body_chars=20)
    by_id = {t.topic_id.upper(): t for t in topics}
    title_to_id: dict[str, str] = {}
    for tid, title in index_titles.items():
        title_to_id[title.casefold().strip()] = tid.upper()
    for t in topics:
        title_to_id[t.title.casefold().strip()] = t.topic_id.upper()
        title_to_id[t.topic_id.casefold()] = t.topic_id.upper()
    return {"by_id": by_id, "title_to_id": title_to_id, "index_titles": index_titles}


def resolve_quiz_tags(
    questions: list[dict[str, Any]],
    *,
    note_text: str = "",
    note_path: str = "",
    default_topic_id: str = "",
    default_concept: str = "",
) -> list[dict[str, Any]]:
    """Attach topic_id, concept, note_path using tags + note topic index."""
    resolver = build_topic_resolver(note_text) if note_text.strip() else None
    default_tid = canonicalize_topic_id(default_topic_id) or ""
    rel_path = canonical_library_path(note_path.replace("\\", "/").strip()) if note_path else ""
    out: list[dict[str, Any]] = []

    for q in questions:
        row = dict(q)
        tid = canonicalize_topic_id(str(row.get("topic_id") or "")) or ""

        for tag in row.get("tags") or []:
            cand = canonicalize_topic_id(str(tag))
            if cand:
                tid = tid or cand
                continue
            if resolver:
                mapped = resolver["title_to_id"].get(str(tag).casefold().strip())
                if mapped:
                    tid = tid or mapped

        if not tid and resolver:
            concept_key = str(row.get("concept") or "").casefold().strip()
            if concept_key and concept_key in resolver["title_to_id"]:
                tid = resolver["title_to_id"][concept_key]

        if not tid and default_tid:
            tid = default_tid

        if tid:
            row["topic_id"] = tid
            title = ""
            if resolver:
                if tid in resolver["by_id"]:
                    title = resolver["by_id"][tid].title
                else:
                    title = resolver["index_titles"].get(tid, "")
                # A tag the note doesn't define is likely a typo or another lecture.
                row["topic_known"] = bool(title)
            if title:
                # The note is authoritative — beats a keyword guess or a bare ID.
                row["concept"] = title[:160]
            elif not row.get("concept") or row.get("concept") in {"Imported", tid}:
                row["concept"] = tid
            row["hint"] = f"Review topic: {row.get('concept') or tid}"

        if default_concept and (not row.get("concept") or row.get("concept") == "Imported"):
            row["concept"] = default_concept[:160]

        if rel_path:
            row["note_path"] = rel_path

        out.append(row)
    return out


def import_summary(questions: list[dict[str, Any]]) -> dict[str, Any]:
    tagged = [q for q in questions if str(q.get("topic_id") or "").strip()]
    topics: dict[str, int] = {}
    unknown: list[str] = []
    for q in tagged:
        tid = str(q["topic_id"])
        topics[tid] = topics.get(tid, 0) + 1
        if q.get("topic_known") is False and tid not in unknown:
            unknown.append(tid)
    return {
        "total": len(questions),
        "tagged": len(tagged),
        "untagged": len(questions) - len(tagged),
        "topics": [{"topic_id": k, "count": v} for k, v in topics.items()],
        "unknown_topics": unknown,
    }


# Back-compat alias
def parse_pasted_mcq_quiz(text: str) -> list[dict[str, Any]]:
    return parse_smart_quiz_import(text)
