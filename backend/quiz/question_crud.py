"""Study Loop question CRUD, open-answer fill, and import parsers.

New packs land under ``data/questions/{kind}/_user/{safe_topic_id}.json``.
Existing question ids are updated in place (authored files included). Imports
are idempotent: the same id is upserted, never duplicated.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from backend import paths
from backend.quiz.atomic_io import atomic_write_text
from backend.quiz.content_bank import load_catalog, normalize_kind
from backend.quiz.content_schemas import SCHEMA_VERSION, ContentFile
from backend.quiz.source_stamp import bump_questions

QUESTIONS_DIR: Path = paths.QUESTIONS_DIR

_UNSAFE_PATH = re.compile(r"[^a-zA-Z0-9._-]+")
_Q_SPLIT = re.compile(r"(?m)^Q\.\s*")


def safe_topic_id(topic_id: str) -> str:
    slug = (topic_id or "").strip().lower()
    slug = _UNSAFE_PATH.sub("_", slug).strip("._-")
    return slug or "untitled"


def _catalog():
    return load_catalog(root=QUESTIONS_DIR, refresh=True)


def _write_json(path: Path, data: dict[str, Any]) -> ContentFile:
    try:
        parsed = ContentFile.model_validate(data)
    except ValidationError as exc:
        first = exc.errors()[0] if exc.errors() else {}
        where = ".".join(str(p) for p in (first.get("loc") or []))
        raise ValueError(f"{where}: {first.get('msg', 'invalid')}".strip(": ")) from exc
    dump = {
        "schema_version": SCHEMA_VERSION,
        "kind": parsed.kind,
        "topic": parsed.topic.model_dump(mode="json"),
        "questions": list(data["questions"]),
    }
    atomic_write_text(path, json.dumps(dump, indent=2, ensure_ascii=False) + "\n")
    bump_questions()
    load_catalog(root=QUESTIONS_DIR, refresh=True)
    return parsed


def _read_pack(path: Path) -> dict[str, Any]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("pack must be a JSON object")
    return raw


def _locate_question(question_id: str) -> tuple[Path, dict[str, Any], int] | None:
    want = (question_id or "").strip()
    if not want:
        return None
    catalog = _catalog()
    for topic in catalog.topics:
        path = QUESTIONS_DIR / topic.source_file
        if not path.is_file():
            continue
        data = _read_pack(path)
        for idx, q in enumerate(data.get("questions") or []):
            if isinstance(q, dict) and str(q.get("id") or "") == want:
                return path, data, idx
    return None


def _user_pack_path(kind: str, topic_id: str) -> Path:
    return QUESTIONS_DIR / kind / "_user" / f"{safe_topic_id(topic_id)}.json"


def _new_envelope(
    *,
    kind: str,
    topic_id: str,
    topic_title: str,
    note_topic_ids: list[str],
    questions: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "kind": kind,
        "topic": {
            "topic_id": topic_id,
            "title": topic_title or topic_id,
            "note_topic_ids": list(note_topic_ids),
            "path": [],
        },
        "questions": questions,
    }


def list_questions(*, tag: str | None, kind: str | None) -> list[dict]:
    catalog = _catalog()
    want_kind = normalize_kind(kind) if kind else None
    want = (tag or "").strip()
    want_u = want.upper()
    out: list[dict] = []
    for topic in catalog.topics:
        if want_kind and topic.kind != want_kind:
            continue
        note_ids = list(topic.note_topic_ids)
        note_u = {t.upper() for t in note_ids}
        for item in topic.items:
            tags = [str(t) for t in (item.get("tags") or [])]
            if want:
                hit = (
                    want in tags
                    or want in note_ids
                    or want_u in {t.upper() for t in tags}
                    or want_u in note_u
                )
                if not hit:
                    continue
            row = dict(item)
            if "note_topic_ids" not in row:
                row["note_topic_ids"] = note_ids
            answer = str(row.get("expected_answer") or row.get("answer") or "").strip()
            fmt = str(row.get("answer_format") or "")
            row["open"] = fmt == "open" or not answer
            out.append(row)
    return out


def upsert_question(payload: dict) -> dict:
    kind = normalize_kind(str(payload.get("kind") or ""))
    if kind not in {"math", "coding", "mcq", "coding_mcq"}:
        raise ValueError(f"unsupported kind {kind!r}")
    topic_id = str(payload.get("topic_id") or "").strip().lower()
    if not topic_id:
        raise ValueError("topic_id is required")
    topic_title = str(payload.get("topic_title") or topic_id)
    note_topic_ids = [str(t) for t in (payload.get("note_topic_ids") or [])]
    question = dict(payload.get("question") or {})
    qid = str(question.get("id") or "").strip()
    if not qid:
        raise ValueError("question.id is required")
    question["id"] = qid

    located = _locate_question(qid)
    if located:
        path, data, idx = located
        merged = {**data["questions"][idx], **question}
        data["questions"][idx] = merged
        topic = dict(data.get("topic") or {})
        existing_notes = [str(t) for t in (topic.get("note_topic_ids") or [])]
        for t in note_topic_ids:
            if t not in existing_notes:
                existing_notes.append(t)
        topic["note_topic_ids"] = existing_notes
        if topic_title and not topic.get("title"):
            topic["title"] = topic_title
        data["topic"] = topic
        _write_json(path, data)
        return dict(data["questions"][idx])

    path = _user_pack_path(kind, topic_id)
    if path.is_file():
        data = _read_pack(path)
        data["questions"] = list(data.get("questions") or [])
        data["questions"].append(question)
        topic = dict(data.get("topic") or {})
        existing_notes = [str(t) for t in (topic.get("note_topic_ids") or [])]
        for t in note_topic_ids:
            if t not in existing_notes:
                existing_notes.append(t)
        topic["note_topic_ids"] = existing_notes
        if topic_title:
            topic["title"] = topic.get("title") or topic_title
        data["topic"] = topic
        data["kind"] = kind
        _write_json(path, data)
        return dict(question)

    envelope = _new_envelope(
        kind=kind,
        topic_id=topic_id,
        topic_title=topic_title,
        note_topic_ids=note_topic_ids,
        questions=[question],
    )
    _write_json(path, envelope)
    return dict(question)


def patch_question(question_id: str, fields: dict) -> dict:
    located = _locate_question(question_id)
    if located is None:
        raise FileNotFoundError(f"question not found: {question_id}")
    path, data, idx = located
    blocked = {"id"}
    updates = {k: v for k, v in (fields or {}).items() if k not in blocked}
    data["questions"][idx] = {**data["questions"][idx], **updates}
    _write_json(path, data)
    return dict(data["questions"][idx])


def delete_question(question_id: str) -> dict:
    located = _locate_question(question_id)
    if located is None:
        raise FileNotFoundError(f"question not found: {question_id}")
    path, data, idx = located
    data["questions"].pop(idx)
    if not data["questions"]:
        path.unlink(missing_ok=True)
        bump_questions()
        load_catalog(root=QUESTIONS_DIR, refresh=True)
        return {"deleted": True, "id": question_id, "pack_removed": True}
    _write_json(path, data)
    return {"deleted": True, "id": question_id, "pack_removed": False}


def _parse_mcq_markdown(text: str) -> list[dict[str, Any]]:
    chunks = _Q_SPLIT.split(text or "")
    out: list[dict[str, Any]] = []
    for chunk in chunks:
        chunk = chunk.strip()
        if not chunk:
            continue
        prompt_parts: list[str] = []
        options: list[str] = []
        answer_index = 0
        for line in chunk.splitlines():
            stripped = line.strip()
            if not stripped:
                continue
            if stripped.startswith("-"):
                opt = stripped[1:].strip()
                correct = False
                if opt.startswith("(*)"):
                    correct = True
                    opt = opt[3:].strip()
                elif opt.startswith("*"):
                    correct = True
                    opt = opt[1:].strip()
                if correct:
                    answer_index = len(options)
                options.append(opt)
            elif not options:
                prompt_parts.append(stripped)
        if len(options) < 2 or not prompt_parts:
            continue
        out.append(
            {
                "question": " ".join(prompt_parts),
                "options": options,
                "answer_index": answer_index,
            }
        )
    return out


def _coerce_questions(
    raw: dict | list | str,
    *,
    kind: str,
    topic_id: str,
) -> tuple[list[dict[str, Any]], str]:
    title = topic_id
    if isinstance(raw, str):
        text = raw.strip()
        if not text:
            return [], title
        if text[:1] in "{[":
            try:
                raw = json.loads(text)
            except json.JSONDecodeError:
                return _parse_mcq_markdown(text), title
        else:
            return _parse_mcq_markdown(text), title

    questions: list[dict[str, Any]] = []
    if isinstance(raw, list):
        questions = [dict(q) for q in raw if isinstance(q, dict)]
    elif isinstance(raw, dict):
        if isinstance(raw.get("questions"), list):
            questions = [dict(q) for q in raw["questions"] if isinstance(q, dict)]
            topic = raw.get("topic") if isinstance(raw.get("topic"), dict) else {}
            title = str(topic.get("title") or raw.get("topic_title") or title)
        elif raw.get("id") or raw.get("question") or raw.get("problem") or raw.get("prompt"):
            questions = [dict(raw)]
    _ = kind
    return questions, title


def import_questions(
    raw: dict | list | str,
    *,
    kind: str,
    topic_id: str,
    note_topic_ids: list[str],
) -> dict:
    kind_n = normalize_kind(kind)
    topic_id = (topic_id or "").strip().lower()
    questions, title = _coerce_questions(raw, kind=kind_n, topic_id=topic_id)
    catalog = _catalog()
    existing_ids = {item["id"] for t in catalog.topics for item in t.items}
    imported = 0
    updated = 0
    errors: list[dict[str, str]] = []
    for i, q in enumerate(questions, start=1):
        qid = str(q.get("id") or "").strip() or f"{topic_id}.q{i:03d}"
        q = {**q, "id": qid}
        payload = {
            "kind": kind_n,
            "topic_id": topic_id,
            "topic_title": title,
            "note_topic_ids": list(note_topic_ids or []),
            "question": q,
        }
        existed = qid in existing_ids
        try:
            upsert_question(payload)
        except (ValueError, ValidationError, OSError) as exc:
            errors.append({"id": qid, "error": str(exc)})
            continue
        if existed:
            updated += 1
        else:
            imported += 1
            existing_ids.add(qid)
    return {"imported": imported, "updated": updated, "errors": errors, "count": len(existing_ids)}
