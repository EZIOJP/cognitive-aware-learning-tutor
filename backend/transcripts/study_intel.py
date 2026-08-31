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


# Below this many chars across selected notes, auto-pull sibling .md files from the same folder.
QUIZ_MIN_CHARS = 800
QUIZ_MAX_FILES = 8


def _note_char_count(relative_path: str, *, max_read: int = 50_000) -> int:
    try:
        path = resolve_notes_path(relative_path.replace("\\", "/").strip())
        if not path.is_file():
            return 0
        # Fast path for large files
        size = path.stat().st_size
        if size <= max_read:
            return len(path.read_text(encoding="utf-8", errors="ignore"))
        return size  # approximate — enough to decide expansion
    except Exception:  # noqa: BLE001
        return 0


def expand_quiz_source_paths(
    primary_paths: list[str],
    *,
    min_chars: int = QUIZ_MIN_CHARS,
    max_files: int = QUIZ_MAX_FILES,
) -> list[str]:
    """
    Keep user-selected notes first. If total material is thin (< min_chars),
    add other .md files from the same folder (longest first) up to max_files.
    Never uses corpus RAG — disk notes only.
    """
    from backend.transcripts.note_topics import canonical_library_path

    ordered: list[str] = []
    seen: set[str] = set()
    for raw in primary_paths:
        p = canonical_library_path((raw or "").replace("\\", "/").strip())
        if not p or p in seen or ".." in p:
            continue
        ordered.append(p)
        seen.add(p)
    if not ordered:
        return []

    total = sum(_note_char_count(p) for p in ordered)
    if total >= min_chars:
        return ordered[:max_files]

    folder = "/".join(ordered[0].split("/")[:-1])
    siblings = list_notes_in_folder(folder, recursive=False)
    scored: list[tuple[int, str]] = []
    for s in siblings:
        if s in seen:
            continue
        scored.append((_note_char_count(s), s))
    scored.sort(key=lambda t: (-t[0], t[1]))

    for n_chars, path in scored:
        if len(ordered) >= max_files or total >= min_chars:
            break
        ordered.append(path)
        seen.add(path)
        total += n_chars

    return ordered[:max_files]


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
    source_types: list[str] | None = None,
) -> list[dict[str, Any]]:
    """Retrieve grounded chunks when corpus RAG is enabled and populated."""
    try:
        from backend.config import get_settings
        from backend.corpus.retrieve import NOTES_RAG_SOURCE_TYPES, corpus_available, hybrid_retrieve

        settings = get_settings()
        if not (settings.corpus_grounded_notes or settings.corpus_study_intel):
            return []
        if not corpus_available():
            return []
        query = (topic or "study material").strip()[:300]
        if boost_concepts:
            query = f"{query} {' '.join(boost_concepts[:6])}"
        types = source_types if source_types is not None else list(NOTES_RAG_SOURCE_TYPES)
        return hybrid_retrieve(query, top_k=5, source_types=types)
    except Exception:  # noqa: BLE001
        return []


def _corpus_material_for_topic(
    topic: str,
    *,
    max_chars: int = 12000,
    boost_concepts: list[str] | None = None,
    source_types: list[str] | None = None,
) -> str | None:
    from backend.corpus.retrieve import format_hits_for_prompt

    hits = _corpus_hits_for_topic(
        topic,
        max_chars=max_chars,
        boost_concepts=boost_concepts,
        source_types=source_types,
    )
    if not hits:
        return None
    return format_hits_for_prompt(hits, max_chars=max_chars)


def _clean_quiz_note_material(text: str, label: str = "") -> str:
    """Remove repeated generated sections and filename-only H1 titles before quiz generation."""
    label_stem = label.replace("\\", "/").rsplit("/", 1)[-1].rsplit(".", 1)[0]
    label_stem = re.sub(r"_20\d{6}_\d{6}$", "", label_stem)
    label_key = re.sub(r"[^a-z0-9]+", " ", label_stem.casefold()).strip()
    seen: set[str] = set()
    kept: list[str] = []
    for raw in (text or "").splitlines():
        stripped = raw.strip()
        if not stripped:
            if kept and kept[-1] != "":
                kept.append("")
            continue
        if stripped.startswith("# "):
            title_key = re.sub(r"[^a-z0-9]+", " ", stripped[2:].casefold()).strip()
            if label_key and title_key == label_key:
                continue
        key = re.sub(r"[^a-z0-9`]+", " ", stripped.casefold()).strip()
        if key and key in seen:
            continue
        if key:
            seen.add(key)
        kept.append(raw)
    return "\n".join(kept).strip()


def _combined_source_material(
    source_texts: list[str],
    *,
    topic: str = "",
    max_chars: int = 16000,
    boost_concepts: list[str] | None = None,
    prefer_notes: bool = False,
    source_types: list[str] | None = None,
    source_labels: list[str] | None = None,
    use_corpus: bool | None = None,
) -> tuple[str, list[dict[str, Any]]]:
    """
    Build prompt material from open note file(s).

    Corpus RAG is OFF by default for study intel (quiz/drills). Open-note quizzes
    (prefer_notes=True) never mix corpus. Enable with CORPUS_STUDY_INTEL=1 or
    use_corpus=True when you intentionally want textbook chunks.
    """
    from backend.config import get_settings
    from backend.corpus.retrieve import NOTES_RAG_SOURCE_TYPES, format_hits_for_prompt

    parts: list[str] = []
    for i, raw in enumerate(source_texts):
        label = ""
        if source_labels and i < len(source_labels) and source_labels[i]:
            label = str(source_labels[i])
        text = _clean_quiz_note_material(raw or "", label)
        if not text:
            continue
        header = f"<!-- note_file: {label} -->\n" if label else "<!-- note_file -->\n"
        parts.append(f"{header}{text}")
    note_text = "\n\n---\n\n".join(parts).strip()
    if len(note_text) > max_chars:
        note_text = note_text[:max_chars] + "\n\n… [truncated]"

    # Open-note library quiz: notes only. Otherwise respect setting / explicit flag.
    if prefer_notes:
        allow_corpus = False
    elif use_corpus is not None:
        allow_corpus = use_corpus
    else:
        allow_corpus = bool(get_settings().corpus_study_intel)

    if not allow_corpus:
        return note_text, []

    types = source_types if source_types is not None else list(NOTES_RAG_SOURCE_TYPES)
    hits = _corpus_hits_for_topic(
        topic,
        max_chars=max_chars,
        boost_concepts=boost_concepts,
        source_types=types,
    )
    corpus_budget = max_chars // 2 if note_text else max_chars
    corpus_part = format_hits_for_prompt(hits, max_chars=corpus_budget) if hits else ""

    if note_text and corpus_part:
        combined = f"{note_text}\n\n---\n\n{corpus_part}".strip()
        return combined[:max_chars], hits
    if corpus_part:
        return corpus_part[:max_chars], hits
    return note_text, []


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
    llm_tier: str | None = None,
    confirm_heavy_budget: bool = False,
) -> dict[str, Any]:
    if not ollama_available(llm):
        return _template_gap_analysis(lecture_text, reference_text)

    prompt = f"""Compare these two study documents. The first is student lecture notes; the second is reference material (textbook/slides).

Return JSON only with keys:
- summary (string, 2-3 sentences)
- gaps (array of objects with: topic, lecture_excerpt, reference_excerpt, severity ["high"|"medium"|"low"], suggestion)
- aligned_topics (array of strings â€” topics both cover well)

Limit gaps to at most 8 items. Use short excerpts (under 120 chars each).

LECTURE NOTES:
{lecture_text[:14000]}

REFERENCE:
{reference_text[:14000]}"""

    raw = ollama_generate(
        prompt,
        timeout=120.0,
        llm=llm,
        task="gap_analysis",
        tier=llm_tier,
        confirm_heavy_budget=confirm_heavy_budget,
    )
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


_JUNK_OPTION_LABELS = {
    "description",
    "why they matter",
    "housekeeping",
    "setup",
    "recap of previous lecture",
    "topics covered",
    "overview",
    "summary",
    "agenda",
    "table of contents",
    "python list vs numpy array",
    "note",
    "example",
}


def _normalize_claim_text(text: str) -> str:
    clean = re.sub(r"\s+", " ", text or "").strip()
    clean = re.sub(r"\*\*(.*?)\*\*", r"\1", clean)
    clean = re.sub(r"`([^`]+)`", r"\1", clean)
    clean = re.sub(r"^note:\s*", "", clean, flags=re.I)
    return clean.strip(" :;-*>")


def _is_junk_claim(text: str) -> bool:
    clean = _normalize_claim_text(text)
    low = clean.casefold()
    if len(clean) < 24 or len(clean) > 280:
        return True
    if low in _JUNK_OPTION_LABELS:
        return True
    junk_markers = (
        "today's numpy topics",
        "per the class outline",
        "whatsapp",
        "notice board",
        "housekeeping",
        "import numpy",
        "graph lr",
        "subgraph",
        "verified line-by-line",
    )
    if any(marker in low for marker in junk_markers):
        return True
    # Outline / comma-list agenda lines are not teaching claims.
    if clean.count(",") >= 3 and ("indexing" in low or "reshape" in low or "aggregate" in low):
        return True
    if clean.count("`") >= 3 and ":" in clean and len(clean) > 120:
        return True
    return False


def _is_junk_option(text: str) -> bool:
    clean = _normalize_claim_text(text)
    low = clean.casefold()
    if not clean or low in _JUNK_OPTION_LABELS:
        return True
    if len(clean) < 2:
        return True
    if clean.endswith(":") and len(clean) < 40:
        return True
    return False


def _extract_note_facts(sources: list[str]) -> list[dict[str, str]]:
    """Extract unique teaching claims — never filename titles or outline agendas."""
    facts: list[dict[str, str]] = []
    seen: set[str] = set()
    section = ""
    skip_sections = {
        "topics covered",
        "overview",
        "summary",
        "agenda",
        "table of contents",
        "housekeeping",
        "setup",
        "recap of previous lecture",
    }

    def add(text: str, *, term: str = "", section_name: str = "") -> None:
        clean = _normalize_claim_text(text)
        if _is_junk_claim(clean):
            return
        term_clean = _normalize_claim_text(term)
        if term_clean.casefold() in _JUNK_OPTION_LABELS:
            term_clean = ""
        key = re.sub(r"[^a-z0-9]+", " ", clean.casefold()).strip()
        if not key or key in seen:
            return
        seen.add(key)
        facts.append(
            {
                "section": section_name or section,
                "term": term_clean,
                "text": clean,
            }
        )

    in_code = False
    for source in sources:
        for raw in (source or "").splitlines():
            line = raw.strip()
            if line.startswith("```"):
                in_code = not in_code
                continue
            if in_code or not line or line.startswith("<!--"):
                continue
            heading = re.match(r"^(#{1,6})\s+(.+)$", line)
            if heading:
                if len(heading.group(1)) >= 2:
                    candidate = heading.group(2).strip()
                    # Drop leading section numbers like "2. Indexing"
                    candidate = re.sub(r"^\d+(\.\d+)*\.\s*", "", candidate)
                    section = "" if candidate.casefold() in skip_sections else candidate
                continue
            if re.fullmatch(r">?\s*\*\*([^*]{2,80}):\*\*", line):
                continue
            bullet = re.match(r"^[-*]\s+(.+)$", line)
            body = bullet.group(1).strip() if bullet else line
            body = body.lstrip("> ").strip()
            labeled = re.match(r"^\*\*([^*]{2,80}):\*\*\s*(.+)$", body)
            if labeled:
                add(labeled.group(2), term=labeled.group(1), section_name=section)
                continue
            for sentence in re.split(r"(?<=[.!?])\s+(?=[A-Z`\"'])", body):
                add(sentence, section_name=section)
    return facts


def _rotate_options(correct: str, distractors: list[str], index: int) -> tuple[list[str], int]:
    unique: list[str] = []
    for option in [correct, *distractors]:
        clipped = _clip(_normalize_claim_text(option), 160)
        if not clipped or _is_junk_option(clipped):
            continue
        if clipped.casefold() not in {o.casefold() for o in unique}:
            unique.append(clipped)
    fillers = [
        "Python-level element-by-element loops over a list",
        "One-based indexing that starts at position 1",
        "Storing mixed types in non-contiguous memory",
        "Silently returning None for missing positions",
    ]
    for filler in fillers:
        if len(unique) >= 4:
            break
        if filler.casefold() not in {o.casefold() for o in unique}:
            unique.append(filler)
    while len(unique) < 4:
        unique.append(f"A detail not supported by these notes ({len(unique)})")
    options = unique[:4]
    correct_clip = _clip(_normalize_claim_text(correct), 160)
    if correct_clip not in options:
        options[0] = correct_clip
    rotation = index % len(options)
    options = options[rotation:] + options[:rotation]
    return options, options.index(correct_clip)


def _initiative_questions_from_facts(
    facts: list[dict[str, str]],
    *,
    topic: str,
    count: int,
) -> list[dict[str, Any]]:
    """Turn teaching claims into why/when/what-happens questions — never cloze blanks."""
    n = max(1, min(int(count or 1), 50))
    answer_pool = [f["text"] for f in facts if not _is_junk_claim(f["text"])]
    candidates: list[dict[str, Any]] = []
    used_prompts: set[str] = set()

    def add_question(
        prompt: str,
        correct: str,
        distractors: list[str],
        *,
        concept: str,
        explanation: str,
    ) -> None:
        if not prompt or not correct or _is_junk_option(correct):
            return
        key = re.sub(r"[^a-z0-9]+", " ", prompt.casefold()).strip()
        if not key or key in used_prompts:
            return
        if "completes this claim" in prompt.casefold() or "____" in prompt:
            return
        options, answer_index = _rotate_options(correct, distractors, len(candidates))
        if any(_is_junk_option(o) for o in options):
            return
        used_prompts.add(key)
        candidates.append(
            {
                "id": f"q{len(candidates) + 1}",
                "question": _clip(prompt, 420),
                "options": options,
                "answer_index": answer_index,
                "explanation": _clip(explanation, 400),
                "hint": f"Review topic: {_clip(concept or topic or 'lecture', 80)}",
                "source_chunk_id": "",
                "citation": "",
                "concept": _clip(concept or topic or "lecture", 80),
            }
        )

    # Pattern pack: important lecture initiatives first (speed, scalar type, slicing, errors).
    patterns: list[tuple[str, str, str, list[str]]] = [
        (
            r"(faster|speed).*(list|contiguous|homogeneous|vectorized)|(contiguous|homogeneous).*(faster|speed|vectorized)",
            "Why are NumPy arrays typically faster than Python lists?",
            "Homogeneous contiguous memory enables vectorized operations",
            [
                "They store each value as a Python object with extra metadata",
                "They always use one-based indexing",
                "They convert every value to text before computing",
            ],
        ),
        (
            r"np\.int64|numpy scalar|not plain python int|not a native python type",
            "When you index a single element of a NumPy array, what do you typically get back?",
            "A NumPy scalar type such as np.int64, not a plain Python int",
            [
                "A plain Python int",
                "A Python list with one item",
                "A string representation of the value",
            ],
        ),
        (
            r"end is always excluded|end.*excluded|start:end",
            "In NumPy slicing `array[start:end]`, what is true about `end`?",
            "`end` is excluded — the slice stops before that index",
            [
                "`end` is included — the slice stops at that index",
                "`end` wraps around from the start",
                "`end` must always equal the array length",
            ],
        ),
        (
            r"indexerror|out of bounds",
            "What happens if direct indexing asks for a position outside the array?",
            "Python raises an IndexError immediately",
            [
                "NumPy silently returns None",
                "NumPy wraps around and returns the first element",
                "NumPy pads the array with zeros",
            ],
        ),
        (
            r"fancy indexing|explicit list of positions",
            "How does fancy indexing differ from a normal slice?",
            "Fancy indexing selects an explicit list of positions (and can repeat indices)",
            [
                "Fancy indexing always excludes the end index only",
                "Fancy indexing only works on Python lists",
                "Fancy indexing changes dtype to string",
            ],
        ),
        (
            r"primary objective of eda|not to prove a hypothesis|exploratory data analysis",
            "What is the primary goal of EDA in these notes?",
            "Understand structure, patterns, and relationships — not prove a hypothesis",
            [
                "Prove a pre-chosen hypothesis as quickly as possible",
                "Train a final production model immediately",
                "Replace all numerical data with text labels",
            ],
        ),
        (
            r"pandas.+data manip|data manip.+pandas|cleaning, filtering",
            "In the data-science pipeline from the notes, what is Pandas mainly used for?",
            "Data manipulation / transforming structures (cleaning, filtering)",
            [
                "Only matrix multiplication",
                "Only drawing plots",
                "Only training neural nets",
            ],
        ),
        (
            r"negative index|w\[-1\]|second-last|idiomatic way",
            "Why prefer `w[-1]` when you need the last element of a NumPy array?",
            "Negative indexing is the idiomatic way to reach the end without computing len(w)-1",
            [
                "Negative indexes are one-based and safer",
                "Negative indexes convert the array to a list first",
                "Negative indexes avoid IndexError in all cases",
            ],
        ),
    ]

    blob = "\n".join(f["text"] for f in facts)
    for pattern, prompt, correct, distractors in patterns:
        if len(candidates) >= n:
            break
        if not re.search(pattern, blob, flags=re.I):
            continue
        matched = next(
            (f for f in facts if re.search(pattern, f["text"], flags=re.I)),
            {"section": topic, "text": correct},
        )
        add_question(
            prompt,
            correct,
            distractors,
            concept=matched.get("section") or topic or "lecture",
            explanation=matched.get("text") or correct,
        )

    # Remaining strong claims → initiative stems (why / when / what if), never fill-in-the-blank.
    for fact in facts:
        if len(candidates) >= n:
            break
        text = fact["text"]
        section = fact["section"] or topic or "this lecture"
        low = text.casefold()

        idx = re.search(r"\b([A-Za-z_]\w*)\[(\d+)\]", text)
        if idx and "index" in (section + " " + text).casefold():
            base, pos = idx.group(1), int(idx.group(2))
            add_question(
                f"Using zero-based indexing from the notes, which expression reads position {pos + 1} of {base}?",
                f"{base}[{pos}]",
                [f"{base}[{pos + 1}]", f"{base}[{max(0, pos - 1)}]", f"{base}({pos})"],
                concept=section,
                explanation=text,
            )
            continue

        if "because" in low:
            left, right = re.split(r"\bbecause\b", text, maxsplit=1, flags=re.I)
            premise = left.strip(" .")
            reason = right.strip(" .")
            if len(premise) >= 12 and len(reason) >= 12:
                add_question(
                    f"Why {premise[:1].lower() + premise[1:]}?",
                    reason,
                    [a for a in answer_pool if a.casefold() != text.casefold()][:3],
                    concept=section,
                    explanation=text,
                )
                continue

        if re.search(r"\b(should|must|prefer|use|avoid|raises?|returns?)\b", low):
            add_question(
                f"When working with {section}, which practice do the notes support?",
                text,
                [a for a in answer_pool if a.casefold() != text.casefold()][:3],
                concept=section,
                explanation=text,
            )
            continue

        add_question(
            f"A classmate is confused about {section}. Which explanation matches the lecture notes?",
            text,
            [a for a in answer_pool if a.casefold() != text.casefold()][:3],
            concept=section,
            explanation=text,
        )

    return candidates[:n]


def _extractive_quiz_from_notes(sources: list[str], count: int, topic: str = "") -> dict[str, Any]:
    """Offline quiz: initiative questions on important topics — never heading/cloze junk."""
    n = max(1, min(int(count or 1), 50))
    facts = _extract_note_facts(sources)
    questions = _initiative_questions_from_facts(facts, topic=topic, count=n)
    if not questions:
        return {"questions": [], "source": "extractive", "concepts": []}
    return {
        "questions": questions,
        "source": "extractive",
        "concepts": [q.get("concept") for q in questions if q.get("concept")],
    }


def _template_quiz(sources: list[str], count: int) -> dict[str, Any]:
    """Deprecated placeholder — prefer _extractive_quiz_from_notes when notes exist."""
    return _extractive_quiz_from_notes(sources, count)


def _normalize_mcq(q: dict[str, Any], *, fallback_id: str, concept: str = "") -> dict[str, Any] | None:
    opts = q.get("options") or []
    if len(opts) < 2:
        return None
    ans = int(q.get("answer_index", 0))
    if ans < 0 or ans >= len(opts):
        ans = 0
    question = str(q.get("question", "")).strip()
    if not question:
        return None
    concept_s = _clip(str(q.get("concept") or concept), 80)
    explanation = _clip(str(q.get("explanation", "")), 400)
    hint = _clip(str(q.get("hint") or ""), 200)
    if not hint and concept_s:
        hint = f"Review topic: {concept_s}"
    return {
        "id": str(q.get("id") or fallback_id),
        "question": _clip(question, 420),
        "options": [_clip(str(o), 160) for o in opts[:6]],
        "answer_index": ans,
        "explanation": explanation,
        "hint": hint,
        "source_chunk_id": str(q.get("source_chunk_id") or ""),
        "concept": concept_s,
    }


def _mcq_quality_key(question: dict[str, Any]) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(question.get("question") or "").casefold()).strip()


def _is_low_quality_mcq(question: dict[str, Any]) -> bool:
    prompt = str(question.get("question") or "").casefold()
    options = [str(option).casefold().strip() for option in question.get("options") or []]
    banned_stems = (
        "which statement best matches",
        "which statement best describes the note section",
        "what topic is covered",
        "completes this claim",
        "____",
        "note section",
    )
    if any(stem in prompt for stem in banned_stems):
        return True
    if any(option.startswith(("it relates to:", "mainly about:")) for option in options):
        return True
    if any(option in _JUNK_OPTION_LABELS for option in options):
        return True
    if any(option.endswith(("`", "(", "[", "{")) or option.startswith((">", "*", "|")) for option in options):
        return True
    return False


def sequential_topic_quota(requested: int, n_topics: int) -> tuple[int, int]:
    """Questions per topic + total target for a sequential walk.

    Always covers every topic (at least 2 questions each) even when ``requested``
    is smaller. Caps total at 160 so a huge note cannot hang forever.
    """
    n = max(1, int(requested or 12))
    if n_topics <= 0:
        return 0, n
    per = max(2, min(4, (n + n_topics - 1) // n_topics))
    target = max(n, per * n_topics)
    return per, min(target, 160)


def _trim_keeping_topics(questions: list[dict[str, Any]], cap: int) -> list[dict[str, Any]]:
    """Keep at least one question per topic_id, then fill remaining slots."""
    if len(questions) <= cap:
        return questions
    keep: list[dict[str, Any]] = []
    extras: list[dict[str, Any]] = []
    seen: set[str] = set()
    for q in questions:
        tid = str(q.get("topic_id") or "").strip()
        if tid and tid not in seen:
            keep.append(q)
            seen.add(tid)
        else:
            extras.append(q)
    out = list(keep)
    for q in extras:
        if len(out) >= cap:
            break
        out.append(q)
    return out[:cap]


def _quiz_call_plan(count: int, focus: str) -> list[tuple[str, int]]:
    """Auto batch plan — specialized roles, max 6 items per call."""
    focus_s = (focus or "mixed").strip().lower()
    max_n = 50 if focus_s == "cover_all" else 25
    n = max(1, min(int(count), max_n))
    if focus_s not in ("mixed", "concept", "coding", "cover_all"):
        focus_s = "mixed"

    def chunk(role: str, total: int) -> list[tuple[str, int]]:
        out: list[tuple[str, int]] = []
        left = total
        while left > 0:
            take = min(6, left)
            out.append((role, take))
            left -= take
        return out

    if focus_s == "cover_all":
        # Whole-topic mix: definitions + concepts + coding + connections.
        definition_n = max(1, n // 4)
        concept_n = max(1, n // 4)
        coding_n = max(1, n // 4)
        connect_n = max(1, n - definition_n - concept_n - coding_n)
        return (
            chunk("definition", definition_n)
            + chunk("concept", concept_n)
            + chunk("coding", coding_n)
            + chunk("connect", connect_n)
        )
    if focus_s == "concept":
        return chunk("concept", n)
    if focus_s == "coding":
        return chunk("coding", n)
    concept_n = (n + 1) // 2
    coding_n = n - concept_n
    return chunk("concept", concept_n) + chunk("coding", coding_n)


def _split_note_sections(
    material: str,
    *,
    max_sections: int = 40,
    max_chars: int = 5500,
    topic_ids: list[str] | None = None,
) -> list[tuple[str, str]]:
    """Split notes into quiz topics (L{n}-Txx preferred; decimal fallback).

    Returns [] when no real topics are found so the caller can use the
    whole-note role plan instead of a fake single \"Full notes\" slice.
    """
    from backend.transcripts.note_topics import parse_note_topics, topics_as_sections

    topics = parse_note_topics(
        material,
        topic_ids=topic_ids,
        max_topics=max_sections,
        max_body_chars=max_chars,
    )
    if topics:
        return topics_as_sections(topics)
    return []


def _quiz_role_prompt(
    *,
    role: str,
    n: int,
    topic: str,
    boost_line: str,
    material: str,
    section_title: str = "",
) -> str:
    shared_rules = """Hard rules:
- Ground EVERY question and the correct option ONLY in the material. No invented APIs or facts.
- Ban bland stems: "What is X?", "Which of the following is true about X?", "completes this claim".
- Distractors must be plausible near-misses (wrong API names, off-by-one indexes, swapped args).
- Each item: 4 option strings; answer_index is 0-based.
- Set "concept" to a short topic label (e.g. "Fancy indexing", "df.to_csv", "NumPy speed").
- Set "hint" to one short coaching tip for that concept (shown when the learner is stuck / wrong).
- Set "explanation" to teach why the correct option wins.
- Do NOT ask about classroom logistics or the speaker.
"""
    section_line = (
        f'\nTHIS TOPIC ONLY ({section_title}) — do not quiz other lecture sections.\n'
        if section_title
        else ""
    )
    if role == "coding":
        focus_block = f"""Create exactly {n} CODING / API practice MCQs from the libraries and examples in the notes
(NumPy, Pandas, Matplotlib, etc. — only what appears in the material).

Prefer:
- "How do you …?" / "Which call …?" / "Write code to …" style
- Realistic distractors like wrong method names (save_csv vs to_csv, intersect vs intersect1d)
- Questions tied to APIs or snippets actually present or clearly implied by the notes
"""
    elif role == "definition":
        focus_block = f"""Create exactly {n} DEFINITION / vocabulary MCQs that check precise meaning of terms in the notes.

Prefer:
- "Which definition matches …?" / "In this lecture, X means …"
- Distinguishing near-synonyms that students confuse
- One correct definition grounded in the notes; distractors are plausible wrong definitions
- Cover DIFFERENT terms in this topic — do not repeat one heading
"""
    elif role == "connect":
        focus_block = f"""Create exactly {n} CONNECTION / synthesis MCQs that link DIFFERENT ideas in the material
(how concept A enables B, what breaks if you confuse two APIs, when to choose approach X vs Y).

Prefer:
- Cross-section questions (do not stay in one heading)
- Apply / compare / debug scenarios grounded in the notes
"""
    else:
        stay = (
            "Stay inside this topic — do not quiz other lecture headings.\n"
            if section_title
            else "- Cover DIFFERENT sections — do not cluster on one heading\n"
        )
        focus_block = f"""Create exactly {n} CONCEPT / initiative MCQs from the lecture notes.

Prefer:
- Why / when / what breaks if / how X connects to Y
{stay}- Scenario questions answerable from the notes (not trivia about the filename)
"""
    return f"""You are a demanding tutor writing a practice quiz from the student's lecture notes.

Topic focus: {topic or "the lecture"}
{boost_line}{section_line}
{focus_block}
{shared_rules}

Return JSON only:
{{"questions":[{{"id":"q1","question":"...","options":["A","B","C","D"],"answer_index":0,"explanation":"...","hint":"...","concept":"...","source_chunk_id":""}}]}}

MATERIAL (source of truth):
{material[:14000]}"""


def _collect_quiz_from_raw(
    raw: str | None,
    *,
    source_hits: list[dict[str, Any]],
    question_keys: set[str],
    start_id: int,
    limit: int,
) -> list[dict[str, Any]]:
    questions: list[dict[str, Any]] = []
    if not raw:
        return questions
    try:
        parsed = _parse_json_blob(raw)
    except (ValueError, json.JSONDecodeError, TypeError):
        return questions
    raw_qs = parsed.get("questions") if isinstance(parsed, dict) else None
    if not isinstance(raw_qs, list) and isinstance(parsed, dict) and parsed.get("question"):
        raw_qs = [parsed]
    for i, q in enumerate(raw_qs or []):
        if len(questions) >= limit:
            break
        if not isinstance(q, dict):
            continue
        normalized = _normalize_mcq(q, fallback_id=f"q{start_id + len(questions)}")
        if not normalized or _is_low_quality_mcq(normalized):
            continue
        quality_key = _mcq_quality_key(normalized)
        if not quality_key or quality_key in question_keys:
            continue
        normalized["citation"] = _citation_for_chunk(
            normalized.get("source_chunk_id") or "", source_hits
        )
        questions.append(normalized)
        question_keys.add(quality_key)
    return questions


def parse_pasted_mcq_quiz(text: str) -> list[dict[str, Any]]:
    """
    Parse copy-pasted web/book quizzes (GeeksforGeeks-style Question N / A B C D blocks).
    """
    blob = (text or "").replace("\r\n", "\n").strip()
    if not blob:
        return []

    # Split on "Question N" headers when present
    parts = re.split(r"(?i)(?:^|\n)\s*question\s+(\d+)\s*", blob)
    blocks: list[str] = []
    if len(parts) > 1:
        # parts: [preamble, num, body, num, body, ...]
        for i in range(2, len(parts), 2):
            blocks.append(parts[i].strip())
    else:
        blocks = [blob]

    letter_re = re.compile(r"(?m)^\s*([A-Da-d])\s*[\).\:\-]\s*(.+?)\s*$")
    questions: list[dict[str, Any]] = []
    for bi, block in enumerate(blocks):
        lines = [ln.rstrip() for ln in block.splitlines() if ln.strip()]
        if not lines:
            continue
        # Drop noise lines
        cleaned: list[str] = []
        for ln in lines:
            low = ln.casefold()
            if low in {"discuss", "comments"} or low.startswith("last updated"):
                continue
            if re.match(r"(?i)^question\s*:?\s*$", ln.strip()):
                continue
            cleaned.append(ln)
        if not cleaned:
            continue

        option_matches = list(letter_re.finditer("\n".join(cleaned)))
        if len(option_matches) < 2:
            continue
        first_opt_line = option_matches[0].group(0)
        # Prompt = text before first option line
        joined = "\n".join(cleaned)
        prompt = joined.split(first_opt_line, 1)[0].strip()
        prompt = re.sub(r"(?i)^question\s*:?\s*", "", prompt).strip()
        if len(prompt) < 8:
            continue
        options: list[str] = []
        for m in option_matches[:6]:
            options.append(m.group(2).strip())
        if len(options) < 2:
            continue
        # Default correct = A unless "Answer:" found
        answer_index = 0
        ans = re.search(r"(?i)answer\s*[:\-]\s*([A-D])\b", block)
        if ans:
            answer_index = ord(ans.group(1).upper()) - ord("A")
            answer_index = max(0, min(answer_index, len(options) - 1))
        concept = ""
        # Light topic guess from keywords
        low_p = prompt.casefold()
        if "numpy" in low_p or "np." in low_p:
            concept = "NumPy"
        elif "pandas" in low_p or "dataframe" in low_p or "df." in low_p:
            concept = "Pandas"
        questions.append(
            {
                "id": f"paste-{bi + 1}",
                "question": _clip(prompt, 420),
                "options": [_clip(o, 160) for o in options],
                "answer_index": answer_index,
                "explanation": "",
                "hint": f"Review topic: {concept}" if concept else "Review this imported question",
                "concept": concept or "Imported",
                "source_chunk_id": "",
                "citation": "pasted",
            }
        )
    return questions


def generate_quiz_items(
    source_texts: list[str],
    *,
    count: int = 12,
    topic: str = "",
    focus: str = "mixed",
    llm: LlmOptions | None = None,
    boost_concepts: list[str] | None = None,
    llm_tier: str | None = None,
    confirm_heavy_budget: bool = False,
    prefer_notes: bool | None = None,
    source_labels: list[str] | None = None,
    topic_ids: list[str] | None = None,
) -> dict[str, Any]:
    """
    Generate MCQs from study notes via role-based AI handler calls (task=quiz_gen).

    Default engine (when the note has topics): walk each topic **in lecture order**
    with a small context window, generate a few MCQs per topic, tag every item
    with topic_id + note_path, then combine. Does not stop after the first N
    topics — covering the outline is the point (can take several LLM calls).
    Optional topic_ids only narrows which topics to walk.
    """
    focus_s = (focus or "mixed").strip().lower()
    if focus_s not in {"mixed", "concept", "coding", "cover_all"}:
        focus_s = "mixed"
    # cover_all is an alias for "walk every topic" — question style stays mixed
    style_focus = "mixed" if focus_s == "cover_all" else focus_s
    requested_n = max(1, min(int(count or 12), 160))
    n = requested_n
    if prefer_notes is None:
        prefer_notes = bool(any((t or "").strip() for t in source_texts))

    primary_note = ""
    if source_labels:
        primary_note = str(source_labels[0] or "").replace("\\", "/").strip()

    # Keep a modest whole-note buffer for connect / fallback only — per-topic
    # calls use small slices (better accuracy, less context load).
    combined, source_hits = _combined_source_material(
        source_texts,
        topic=topic,
        max_chars=16000,
        boost_concepts=boost_concepts,
        prefer_notes=prefer_notes,
        source_labels=source_labels,
    )
    allowed_ids = {h["chunk_id"] for h in source_hits}

    empty = {
        "questions": [],
        "source": "none",
        "focus": focus_s,
        "engine": "topic_loop",
        "call_plan": [],
        "sections_covered": [],
        "topics_covered": [],
        "topic_index": [],
        "concepts": [],
        "llm_calls": 0,
        "questions_from_llm": 0,
        "questions_from_extractive": 0,
        "call_log": [],
        "target_count": n,
        "filled_count": 0,
        "note_path": primary_note or None,
    }

    if not combined.strip():
        fb = _extractive_quiz_from_notes(source_texts or [topic or "study"], n, topic)
        qs = fb.get("questions") or []
        return {
            **empty,
            "questions": qs[:n],
            "source": "extractive",
            "concepts": [q.get("concept") for q in qs[:n] if q.get("concept")],
            "questions_from_extractive": len(qs[:n]),
            "filled_count": len(qs[:n]),
        }

    if not ollama_available(llm):
        fb = _extractive_quiz_from_notes(source_texts or [combined], n, topic)
        qs = fb.get("questions") or []
        return {
            **empty,
            "questions": qs[:n],
            "source": "extractive",
            "concepts": [q.get("concept") for q in qs[:n] if q.get("concept")],
            "questions_from_extractive": len(qs[:n]),
            "filled_count": len(qs[:n]),
        }

    boost_line = ""
    if boost_concepts:
        boost_line = (
            "Prioritize weak / recently missed concepts when they appear in the notes: "
            + ", ".join(str(c) for c in boost_concepts[:8])
            + ".\n"
        )

    plan = _quiz_call_plan(n, style_focus)
    questions: list[dict[str, Any]] = []
    question_keys: set[str] = set()
    call_log: list[dict[str, Any]] = []
    # Prefer topic slices whenever the note has them (L{n}-Txx or decimal).
    # Optional topic_ids only narrows which topics to walk — not a different engine.
    sections = _split_note_sections(
        combined,
        max_sections=40,
        max_chars=3500,  # small context per topic → clearer, more accurate MCQs
        topic_ids=topic_ids,
    )
    use_topic_loop = bool(sections)
    if use_topic_loop:
        per_topic, n = sequential_topic_quota(requested_n, len(sections))
    else:
        per_topic = 0
        n = requested_n
    max_calls = max(64, len(sections) * 6 + 16) if use_topic_loop else max(12, len(plan) * 3)
    empty_streak = 0
    TOPIC_BODY_CAP = 3500

    def _tag_item(item: dict[str, Any], section_title: str = "") -> dict[str, Any]:
        out = dict(item)
        tid = ""
        title = section_title.strip()
        m = re.match(r"^(L\d+-T\d+)\s*[—\-–:]\s*(.+)$", title, re.I)
        if m:
            tid, title = m.group(1).upper(), m.group(2).strip()
        else:
            m = re.match(r"^(\d+(?:\.\d+)*)\s*[—\-–:]\s*(.+)$", title)
            if m:
                tid, title = m.group(1), m.group(2).strip()
            elif re.match(r"^L\d+-T\d+$", title, re.I):
                tid = title.upper()
        if section_title and not out.get("concept"):
            out["concept"] = (title or section_title)[:80]
        if tid:
            out["topic_id"] = tid
            out["topic"] = tid
        elif out.get("concept"):
            out["topic"] = str(out["concept"])[:160]
        if primary_note:
            out["note_path"] = primary_note
        tags: list[str] = []
        if tid:
            tags.append(tid)
        if primary_note:
            tags.append(primary_note)
        concept = str(out.get("concept") or "").strip()
        if concept and concept not in tags:
            tags.append(concept[:80])
        out["tags"] = tags
        if not out.get("hint") and (tid or concept):
            out["hint"] = f"Review topic: {tid or concept}"
        return out

    HARD_CAP = 160

    def _run_batch(
        *,
        role: str,
        need: int,
        material: str,
        section_title: str = "",
        label: str = "",
    ) -> int:
        nonlocal empty_streak
        need = max(0, min(int(need), HARD_CAP - len(questions), 4))
        if need <= 0 or len(call_log) >= max_calls:
            return 0
        material_s = (material or "")[:TOPIC_BODY_CAP]
        prompt = _quiz_role_prompt(
            role=role,
            n=need,
            topic=topic,
            boost_line=boost_line,
            material=material_s,
            section_title=section_title,
        )
        raw = ollama_generate(
            prompt,
            timeout=120.0,
            llm=llm,
            task="quiz_gen",
            tier=llm_tier,
            confirm_heavy_budget=confirm_heavy_budget,
        )
        before = len(questions)
        err = None if raw else "empty_or_failed"
        batch = _collect_quiz_from_raw(
            raw,
            source_hits=source_hits,
            question_keys=question_keys,
            start_id=len(questions) + 1,
            limit=need,
        )
        for item in batch:
            questions.append(_tag_item(item, section_title))
        got = len(questions) - before
        call_log.append(
            {
                "label": label or f"{role}:{need}",
                "role": role,
                "asked": need,
                "got": got,
                "error": err if got == 0 else None,
                "ok": got > 0,
                "context_chars": len(material_s),
            }
        )
        if got <= 0:
            empty_streak += 1
        else:
            empty_streak = 0
        return got

    def _fill_job(
        *,
        role: str,
        quota: int,
        material: str,
        section_title: str = "",
        label: str = "",
    ) -> None:
        """Retry until this job's quota is met (or empty streak / budget)."""
        remaining = max(0, min(int(quota), HARD_CAP - len(questions)))
        attempts = 0
        while remaining > 0 and len(questions) < HARD_CAP and len(call_log) < max_calls:
            if empty_streak >= 4:
                break
            got = _run_batch(
                role=role,
                need=remaining,
                material=material,
                section_title=section_title,
                label=f"{label}#{attempts + 1}" if label else "",
            )
            attempts += 1
            if got <= 0:
                break
            remaining -= got
            if attempts >= 6:
                break

    def _topic_roles() -> list[str]:
        if style_focus == "coding":
            return ["coding"]
        if style_focus == "concept":
            return ["concept", "definition"]
        return ["concept", "coding"]

    def _topic_jobs(quota: int) -> list[tuple[str, int]]:
        quota = max(1, int(quota))
        if style_focus == "coding":
            return [("coding", quota)]
        if style_focus == "concept":
            defn = max(1, quota // 2) if quota >= 2 else 0
            concept_n = quota - defn
            jobs = [("concept", concept_n)]
            if defn:
                jobs.append(("definition", defn))
            return jobs
        concept_n = (quota + 1) // 2
        coding_n = quota - concept_n
        jobs = [("concept", concept_n)]
        if coding_n:
            jobs.append(("coding", coding_n))
        return jobs

    # Primary engine: sequential topic walk (small context), then optional fill.
    if use_topic_loop:
        empty_streak = 0
        for heading, body in sections:
            if len(call_log) >= max_calls or len(questions) >= HARD_CAP:
                break
            for role, quota in _topic_jobs(per_topic):
                if len(call_log) >= max_calls or len(questions) >= HARD_CAP:
                    break
                _fill_job(
                    role=role,
                    quota=min(quota, HARD_CAP - len(questions)),
                    material=body,
                    section_title=heading,
                    label=f"topic:{heading[:48]}",
                )
        if len(questions) < n and empty_streak < 4 and len(sections) >= 2:
            digest = "\n".join(
                f"- {h}\n  {(b[:280]).strip()}" for h, b in sections[:12]
            )[:TOPIC_BODY_CAP]
            _fill_job(
                role="connect",
                quota=min(max(1, n // 10), n - len(questions)),
                material=digest,
                section_title="",
                label="topic:connect",
            )
        # Fill remaining quota by rotating topics (still small context)
        fill_roles = _topic_roles() + (["connect"] if len(sections) >= 2 else [])
        fi = 0
        while len(questions) < n and len(call_log) < max_calls and empty_streak < 6:
            role = fill_roles[fi % len(fill_roles)]
            heading, body = sections[fi % len(sections)]
            fi += 1
            material = body if role != "connect" else combined[:TOPIC_BODY_CAP]
            section_title = heading if role != "connect" else ""
            before = len(questions)
            _run_batch(
                role=role,
                need=min(3, n - len(questions)),
                material=material,
                section_title=section_title,
                label=f"fill:{role}",
            )
            if len(questions) == before:
                break
    else:
        for role, batch_n in plan:
            if len(questions) >= n or empty_streak >= 4:
                break
            _fill_job(
                role=role,
                quota=min(batch_n, n - len(questions)),
                material=combined[:TOPIC_BODY_CAP],
                section_title="",
                label=f"role:{role}",
            )
        fill_roles = ["definition", "concept", "coding", "connect"]
        fi = 0
        while len(questions) < n and len(call_log) < max_calls and empty_streak < 6:
            role = fill_roles[fi % len(fill_roles)]
            fi += 1
            before = len(questions)
            _run_batch(
                role=role,
                need=min(4, n - len(questions)),
                material=combined[:TOPIC_BODY_CAP],
                section_title="",
                label=f"fill:{role}",
            )
            if len(questions) == before:
                break

    llm_count = len(questions)
    if len(questions) < requested_n and llm_count == 0:
        fallback = _extractive_quiz_from_notes(source_texts or [combined], requested_n, topic)
        for item in fallback.get("questions") or []:
            quality_key = _mcq_quality_key(item)
            if not quality_key or quality_key in question_keys or _is_low_quality_mcq(item):
                continue
            item = dict(item)
            item["id"] = f"q{len(questions) + 1}"
            questions.append(_tag_item(item, ""))
            question_keys.add(quality_key)
            if len(questions) >= requested_n:
                break

    extracted = max(0, len(questions) - llm_count)
    tagged = [_tag_item(q) if "tags" not in q else q for q in questions]
    if llm_count == 0:
        final = tagged[:requested_n]
    else:
        final = _trim_keeping_topics(tagged, max(n, 160))
    if llm_count >= min(n, len(final)) and llm_count > 0:
        source = "llm"
    elif llm_count > 0:
        source = "mixed"
    else:
        source = "extractive"

    try:
        from backend.corpus.citation_check import verify_quiz_citations

        verify_quiz_citations(final, allowed_ids)
    except Exception:  # noqa: BLE001
        pass

    topics_covered = []
    topic_index: list[dict[str, Any]] = []
    for h, body in sections:
        m = re.match(r"^(L\d+-T\d+)", h, re.I)
        if m:
            tid = m.group(1).upper()
            title = h.split("—", 1)[-1].strip() if "—" in h else h
            topics_covered.append(tid)
            qn = sum(1 for q in final if str(q.get("topic_id") or "") == tid)
            topic_index.append(
                {"topic_id": tid, "title": title[:120], "question_count": qn, "char_count": len(body)}
            )
            continue
        m2 = re.match(r"^(\d+(?:\.\d+)*)\b", h)
        tid = m2.group(1) if m2 else h[:80]
        topics_covered.append(tid)
        qn = sum(1 for q in final if str(q.get("topic_id") or q.get("topic") or "") == tid)
        topic_index.append(
            {"topic_id": tid, "title": h[:120], "question_count": qn, "char_count": len(body)}
        )

    return {
        "questions": final,
        "source": source,
        "focus": focus_s,
        "engine": "topic_loop" if use_topic_loop else "whole_note",
        "call_plan": [{"role": r, "count": c} for r, c in plan],
        "sections_covered": [h for h, _ in sections] if sections else [],
        "topics_covered": topics_covered,
        "topic_index": topic_index,
        "concepts": [q.get("concept") for q in final if q.get("concept")],
        "llm_calls": len(call_log),
        "questions_from_llm": min(llm_count, len(final)),
        "questions_from_extractive": extracted if len(final) > llm_count else max(0, len(final) - llm_count),
        "call_log": call_log,
        "target_count": n,
        "filled_count": len(final),
        "note_path": primary_note or None,
    }



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
    llm_tier: str | None = None,
    confirm_heavy_budget: bool = False,
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

    raw = ollama_generate(
        prompt,
        timeout=120.0,
        llm=llm,
        task="drill_gen",
        tier=llm_tier,
        confirm_heavy_budget=confirm_heavy_budget,
    )
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


def generate_primer(
    db: Session,
    *,
    user_id: int,
    topic: str,
    folder_path: str = "",
    llm: LlmOptions | None = None,
    llm_tier: str | None = None,
    confirm_heavy_budget: bool = False,
) -> dict[str, Any]:
    """One-page corpus outline before watching a lecture."""
    subject = topic.strip()
    if not subject:
        raise ValueError("Topic is required.")

    from backend.config import get_settings
    from backend.corpus.retrieve import corpus_available, format_hits_for_prompt, hybrid_retrieve

    if not get_settings().corpus_grounded_notes:
        raise ValueError("Corpus RAG is disabled — enable CORPUS_GROUNDED_NOTES=1 for primers.")

    if not corpus_available():
        raise ValueError("Corpus not available — build Knowledge Base first.")

    hits = hybrid_retrieve(subject, top_k=10)
    context = format_hits_for_prompt(hits, max_chars=14_000)
    folder = folder_path.replace("\\", "/").strip()

    if ollama_available(llm):
        prompt = f"""Create a ONE-PAGE study primer outline for: "{subject}"

Use corpus excerpts below. Requirements:
- ## headings only (compact — fits one screen)
- Key terms, prerequisites, and what to watch for in the lecture
- 5–8 bullet takeaways max
- Markdown only; no mermaid unless essential

Corpus:
{context[:14_000]}
"""
        md_raw = ollama_generate(
            prompt,
            llm=llm,
            task="folder_summarize",
            tier=llm_tier,
            confirm_heavy_budget=confirm_heavy_budget,
        )
        md = (md_raw or "").strip()
        if not md.startswith("#"):
            md = f"# Primer — {subject}\n\n{md}"
    else:
        md = (
            f"# Primer — {subject}\n\n"
            f"## Corpus preview\n\n{context[:4000]}\n\n"
            "_Enable local LLM for a synthesized primer outline._\n"
        )

    out_title = f"Primer — {subject}"
    row = create_note_file(
        db,
        user_id=user_id,
        title=out_title,
        folder_path=folder,
        kind="note",
        content=md + "\n",
        topic=subject,
    )
    return {
        "relative_path": note_storage_path(row),
        "title": row.title,
        "markdown": md,
        "corpus_hits": len(hits),
        "source": "llm" if ollama_available(llm) else "template",
    }


def summarize_folder(
    db: Session,
    *,
    user_id: int,
    folder_path: str,
    llm: LlmOptions | None = None,
    title: str | None = None,
    llm_tier: str | None = None,
    confirm_heavy_budget: bool = False,
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

    from backend.quiz.review_cards import weak_concepts_for_retrieval

    if ollama_available(llm):
        weak = weak_concepts_for_retrieval(db, user_id, limit=8)
        weak_block = ""
        if weak:
            weak_block = (
                "\n\n## Weak topics (prioritize in revision pack)\n"
                + ", ".join(weak)
                + "\n"
            )
        prompt = f"""Synthesize these study notes from folder "{folder_name}" into ONE smart folder-level summary.

Requirements:
- Cross-note themes and how ideas connect (not a file-by-file recap)
- Consolidated outline with ## headings
- Deduplicated key definitions, formulas, and takeaways
- Address weak topics from the student's report card when relevant
- Gaps, open questions, and a suggested study sequence
- Markdown only (no JSON). Use mermaid only if it clearly helps.
{weak_block}
Notes:
{combined[:40_000]}
"""
        md_raw = ollama_generate(
            prompt,
            llm=llm,
            task="folder_summarize",
            tier=llm_tier,
            confirm_heavy_budget=confirm_heavy_budget,
        )
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
