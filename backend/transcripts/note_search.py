"""Text-level lecture-note search — topics, functions, and body hits."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Literal

from backend import paths
from backend.transcripts.library import is_indexable_library_note
from backend.transcripts.note_topics import (
    NoteTopic,
    _INDEX_ROW,
    _split_markdown_sections,
    _parse_heading_identity,
    parse_note_topics,
    parse_topic_index,
)


def _note_disk_path(relative_path: str) -> Path | None:
    """Resolve a library note on disk; tolerate stale DB paths after moves."""
    clean = relative_path.replace("\\", "/").lstrip("/")
    if not clean:
        return None
    root = paths.NOTES_DIR.resolve()
    direct = (paths.NOTES_DIR / clean).resolve()
    if direct.is_file() and direct.is_relative_to(root):
        return direct
    name = Path(clean).name
    if not name:
        return None
    for candidate in paths.NOTES_DIR.rglob(name):
        if candidate.is_file() and candidate.suffix.lower() == ".md":
            return candidate
    return None


MatchKind = Literal["topic", "function", "text", "file"]

_FUNC_ROW = re.compile(
    r"^\|\s*`([^`]+)`\s*\|\s*([^|]+?)\s*\|\s*(?:`?(L\d+-T\d+)`?[^|]*)\|",
    re.IGNORECASE | re.MULTILINE,
)


def _snippet_around(text: str, query: str, *, radius: int = 90) -> str:
    q = query.lower()
    body_l = text.lower()
    idx = body_l.find(q)
    if idx < 0:
        return " ".join(text[: radius * 2].split())[: radius * 2]
    start = max(0, idx - radius)
    end = min(len(text), idx + len(query) + radius)
    out = " ".join(text[start:end].split())
    if start > 0:
        out = "…" + out
    if end < len(text):
        out = out + "…"
    return out


def _score_hit(kind: MatchKind, query: str, *, field: str) -> int:
    q = query.lower()
    f = field.lower()
    if kind == "function":
        if f == q:
            return 48
        if q in f and ("." in f or "(" in f):
            return 42
        return 36
    if kind == "topic":
        if q in f:
            return 40
        return 28
    if kind == "file":
        if f == q:
            return 34
        return 22
    # text
    return 18


def _parse_function_rows(material: str) -> list[tuple[str, str, str]]:
    """Return (function_syntax, description, topic_id) from quick-lookup tables."""
    rows: list[tuple[str, str, str]] = []
    for m in _FUNC_ROW.finditer(material or ""):
        func = m.group(1).strip()
        desc = m.group(2).strip()
        tid = (m.group(3) or "").upper()
        if not func or func.lower().startswith("function"):
            continue
        rows.append((func, desc, tid))
    return rows


def _topic_hits(
    query: str,
    *,
    rel: str,
    file_title: str,
    folder_path: str,
    kind: str,
    topics: list[NoteTopic],
    index_titles: dict[str, str],
) -> list[dict[str, Any]]:
    q = query.lower()
    hits: list[dict[str, Any]] = []

    for tid, title in index_titles.items():
        blob = f"{tid} {title}".lower()
        if q not in blob and q not in title.lower():
            continue
        hits.append(
            {
                "relative_path": rel,
                "title": file_title,
                "kind": kind,
                "folder_path": folder_path,
                "topic_id": tid,
                "topic_title": title,
                "match_kind": "topic",
                "label": f"{tid} — {title}",
                "snippet": title,
                "score": _score_hit("topic", query, field=title),
            }
        )

    for topic in topics:
        title_blob = f"{topic.topic_id} {topic.title}".lower()
        if q in title_blob:
            hits.append(
                {
                    "relative_path": rel,
                    "title": file_title,
                    "kind": kind,
                    "folder_path": folder_path,
                    "topic_id": topic.topic_id,
                    "topic_title": topic.title,
                    "match_kind": "topic",
                    "label": topic.as_dict()["label"],
                    "snippet": topic.title,
                    "score": _score_hit("topic", query, field=topic.title),
                }
            )
        elif q in topic.body.lower():
            hits.append(
                {
                    "relative_path": rel,
                    "title": file_title,
                    "kind": kind,
                    "folder_path": folder_path,
                    "topic_id": topic.topic_id,
                    "topic_title": topic.title,
                    "match_kind": "text",
                    "label": topic.as_dict()["label"],
                    "snippet": _snippet_around(topic.body, query),
                    "score": _score_hit("text", query, field=topic.body),
                }
            )

    return hits


def _count_body_matches(body: str, query: str) -> int:
    q = query.strip().lower()
    if not q:
        return 0
    return (body or "").lower().count(q)


def search_note_content(
    query: str,
    *,
    relative_path: str,
    file_title: str,
    folder_path: str,
    kind: str,
    body: str,
) -> list[dict[str, Any]]:
    """Search one note; returns content hits only (topics, functions, section text)."""
    q = query.strip().lower()
    if not q or not body.strip():
        return []

    if q not in body.lower():
        return []

    hits: list[dict[str, Any]] = []
    index_titles = parse_topic_index(body)
    topics = parse_note_topics(body, min_body_chars=1, max_topics=80)

    hits.extend(
        _topic_hits(
            query,
            rel=relative_path,
            file_title=file_title,
            folder_path=folder_path,
            kind=kind,
            topics=topics,
            index_titles=index_titles,
        )
    )

    for func, desc, tid in _parse_function_rows(body):
        blob = f"{func} {desc}".lower()
        if q not in blob and q not in func.lower():
            continue
        topic_title = index_titles.get(tid, "")
        hits.append(
            {
                "relative_path": relative_path,
                "title": file_title,
                "kind": kind,
                "folder_path": folder_path,
                "topic_id": tid,
                "topic_title": topic_title,
                "match_kind": "function",
                "label": func,
                "snippet": desc or func,
                "score": _score_hit("function", query, field=func),
            }
        )

    if not any(h["match_kind"] in ("topic", "text", "function") for h in hits):
        for heading, section_body in _split_markdown_sections(body):
            ident = _parse_heading_identity(heading)
            if not ident:
                continue
            tid, title, _source = ident
            combined = f"{heading}\n{section_body}"
            if q not in combined.lower():
                continue
            hits.append(
                {
                    "relative_path": relative_path,
                    "title": file_title,
                    "kind": kind,
                    "folder_path": folder_path,
                    "topic_id": tid,
                    "topic_title": title,
                    "match_kind": "text",
                    "label": f"{tid} — {title}" if tid else title,
                    "snippet": _snippet_around(section_body or heading, query),
                    "score": _score_hit("text", query, field=combined),
                }
            )

    if not hits:
        hits.append(
            {
                "relative_path": relative_path,
                "title": file_title,
                "kind": kind,
                "folder_path": folder_path,
                "topic_id": "",
                "topic_title": "",
                "match_kind": "text",
                "label": file_title,
                "snippet": _snippet_around(body, query),
                "score": 12,
            }
        )

    return hits


def _folder_from_relative(rel: str) -> str:
    parts = rel.replace("\\", "/").split("/")
    if len(parts) <= 1:
        return ""
    return "/".join(parts[:-1])


def _title_from_relative(rel: str) -> str:
    from pathlib import Path

    return Path(rel).stem.replace("_", " ").strip() or rel


def _is_searchable_md(path) -> bool:
    name = path.name.lower()
    if not name.endswith(".md"):
        return False
    if name.startswith("."):
        return False
    if ".bak" in name:
        return False
    try:
        rel = path.relative_to(paths.NOTES_DIR.resolve()).as_posix()
    except ValueError:
        rel = path.name
    return is_indexable_library_note(rel)


def search_all_notes(
    note_files: list[tuple[str, str, str]],
    query: str,
    *,
    limit: int = 80,
    max_hits_per_file: int = 12,
    kinds: set[str] | None = None,
) -> list[dict[str, Any]]:
    """Search notes; files with the most in-body matches rank first."""
    q = query.strip()
    if not q:
        return []

    q_l = q.lower()
    by_file: dict[str, list[dict[str, Any]]] = {}
    file_rank: dict[str, tuple[int, int, str]] = {}

    for rel, file_title, kind in note_files:
        disk = _note_disk_path(rel)
        if not disk:
            continue
        try:
            body = disk.read_text(encoding="utf-8")
        except OSError:
            continue
        if q_l not in body.lower():
            continue

        body_match_count = _count_body_matches(body, q)
        folder = _folder_from_relative(rel)
        hits = search_note_content(
            q,
            relative_path=rel,
            file_title=file_title,
            folder_path=folder,
            kind=kind,
            body=body,
        )
        if not hits:
            continue

        seen: set[tuple[str, str, str, str]] = set()
        deduped: list[dict[str, Any]] = []
        for hit in hits:
            key = (
                hit.get("topic_id") or "",
                hit["match_kind"],
                hit.get("label") or hit.get("snippet") or "",
                hit["relative_path"],
            )
            if key in seen:
                continue
            seen.add(key)
            hit["body_match_count"] = body_match_count
            hit["section_hit_count"] = len(hits)
            deduped.append(hit)

        deduped.sort(key=lambda h: (-h["score"], h.get("topic_id") or ""))
        if kinds:
            deduped = [h for h in deduped if h["match_kind"] in kinds]
        if not deduped:
            continue
        by_file[rel] = deduped[:max_hits_per_file]
        file_rank[rel] = (-body_match_count, -len(deduped), rel.lower())

    ranked_paths = sorted(by_file.keys(), key=lambda p: file_rank[p])

    out: list[dict[str, Any]] = []
    for rel in ranked_paths:
        out.extend(by_file[rel])

    return out[:limit]
