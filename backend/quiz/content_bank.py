"""Loader for authored question content under ``data/questions/``.

Reads the JSON files described in docs/QUESTION_CONTENT_FORMAT.md, validates them with
``content_schemas``, and normalizes them into the item shape the existing quiz engine
already understands. Nothing here schedules reviews on its own — seeding goes through
``review_cards.seed_content_cards`` so there is exactly one SRS.
"""

from __future__ import annotations

import json
import random
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from backend.paths import QUESTIONS_DIR
from backend.quiz.content_schemas import CONTENT_KINDS, ContentFile

# Item "kind" used inside quiz sessions. The engine has always called code items "code";
# the Questions surface calls them "coding". Both are accepted everywhere.
CODING_KINDS = ("coding", "code")


def normalize_kind(kind: str | None) -> str:
    """Map user-facing / legacy kind names onto the content-bank kind."""
    k = (kind or "").strip().lower()
    if k in CODING_KINDS:
        return "coding"
    if k in ("math", "maths"):
        return "math"
    if k in ("vocab", "vocabulary"):
        return "vocab"
    if k in ("coding_mcq", "code_mcq"):
        return "coding_mcq"
    return k or "mcq"


@dataclass
class TopicEntry:
    kind: str
    topic_id: str
    title: str
    stage: str = ""
    track: str = ""
    path: list[str] = field(default_factory=list)
    prerequisites: list[str] = field(default_factory=list)
    note_topic_ids: list[str] = field(default_factory=list)
    description: str = ""
    question_count: int = 0
    difficulties: dict[str, int] = field(default_factory=dict)
    source_file: str = ""
    items: list[dict[str, Any]] = field(default_factory=list)

    def to_summary(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "topic_id": self.topic_id,
            "title": self.title,
            "stage": self.stage,
            "track": self.track,
            "path": list(self.path),
            "prerequisites": list(self.prerequisites),
            "note_topic_ids": list(self.note_topic_ids),
            "description": self.description,
            "question_count": self.question_count,
            "difficulties": dict(self.difficulties),
            "source_file": self.source_file,
        }


@dataclass
class Catalog:
    topics: list[TopicEntry] = field(default_factory=list)
    errors: list[dict[str, str]] = field(default_factory=list)

    def by_id(self, topic_id: str) -> TopicEntry | None:
        want = (topic_id or "").strip().lower()
        for t in self.topics:
            if t.topic_id == want:
                return t
        return None

    def to_dict(self) -> dict[str, Any]:
        kinds: dict[str, int] = {}
        for t in self.topics:
            kinds[t.kind] = kinds.get(t.kind, 0) + t.question_count
        return {
            "topics": [t.to_summary() for t in self.topics],
            "kinds": kinds,
            "topic_count": len(self.topics),
            "question_count": sum(t.question_count for t in self.topics),
            "errors": self.errors,
        }


def _math_item(topic: TopicEntry, q: Any) -> dict[str, Any]:
    return {
        "kind": "math",
        "id": q.id,
        "prompt": q.problem,
        "expected_answer": q.answer,
        "answer_format": q.answer_format,
        "solution_steps": list(q.solution_steps),
        "difficulty": q.difficulty,
        "explanation": q.explanation,
        "hint": q.hint or q.explanation,
        "topic": topic.topic_id,
        "topic_id": topic.topic_id,
        "topic_title": topic.title,
        "topic_path": list(topic.path),
        "tags": list(q.tags),
        "note_topic_ids": list(topic.note_topic_ids),
        "content_kind": "math",
    }


def _coding_item(topic: TopicEntry, q: Any) -> dict[str, Any]:
    return {
        "kind": "coding",
        "id": q.id,
        "title": q.title,
        "prompt": q.prompt,
        "language": q.language,
        "entry_point": q.entry_point,
        "starter_code": q.starter_code or "# your code\n",
        "setup_code": q.setup_code,
        "solution": q.solution,
        "difficulty": q.difficulty,
        "explanation": q.explanation,
        "hint": q.hint,
        "test_cases": [c.model_dump() for c in q.test_cases],
        "topic": topic.topic_id,
        "topic_id": topic.topic_id,
        "topic_title": topic.title,
        "topic_path": list(topic.path),
        "tags": list(q.tags),
        "note_topic_ids": list(topic.note_topic_ids),
        "content_kind": "coding",
    }


def _mcq_item(topic: TopicEntry, q: Any) -> dict[str, Any]:
    return {
        "kind": "mcq",
        "id": q.id,
        "question": q.question,
        "options": list(q.options),
        "answer_index": q.answer_index,
        "difficulty": q.difficulty,
        "explanation": q.explanation,
        "hint": q.hint,
        "topic": topic.topic_id,
        "topic_id": topic.topic_id,
        "tags": list(q.tags),
        "note_topic_ids": list(topic.note_topic_ids),
        "content_kind": "mcq",
    }


def _coding_mcq_item(topic: TopicEntry, q: Any) -> dict[str, Any]:
    return {
        "kind": "coding_mcq",
        "id": q.id,
        "prompt": q.prompt,
        "options": list(q.options),
        "answer_index": q.answer_index,
        "starter_code": q.starter_code,
        "difficulty": q.difficulty,
        "explanation": q.explanation,
        "hint": q.hint,
        "topic": topic.topic_id,
        "topic_id": topic.topic_id,
        "tags": list(q.tags),
        "note_topic_ids": list(topic.note_topic_ids),
        "content_kind": "coding_mcq",
    }


_ITEM_BUILDERS = {
    "math": _math_item,
    "coding": _coding_item,
    "mcq": _mcq_item,
    "coding_mcq": _coding_mcq_item,
}


def _read_file(path: Path, root: Path) -> tuple[TopicEntry | None, dict[str, str] | None]:
    rel = path.relative_to(root).as_posix()
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return None, {"file": rel, "error": f"unreadable JSON: {exc}"}
    if not isinstance(raw, dict):
        return None, {"file": rel, "error": "top level must be a JSON object"}
    try:
        parsed = ContentFile.model_validate(raw)
    except ValidationError as exc:
        first = exc.errors()[0] if exc.errors() else {}
        where = ".".join(str(p) for p in (first.get("loc") or []))
        return None, {"file": rel, "error": f"{where}: {first.get('msg', 'invalid')}".strip(": ")}

    topic = TopicEntry(
        kind=parsed.kind,
        topic_id=parsed.topic.topic_id,
        title=parsed.topic.title,
        stage=parsed.topic.stage,
        track=parsed.topic.track,
        path=list(parsed.topic.path),
        prerequisites=list(parsed.topic.prerequisites),
        note_topic_ids=list(parsed.topic.note_topic_ids),
        description=parsed.topic.description,
        source_file=rel,
    )
    build = _ITEM_BUILDERS[parsed.kind]
    for q in parsed.parsed_questions:
        topic.items.append(build(topic, q))
        topic.difficulties[q.difficulty] = topic.difficulties.get(q.difficulty, 0) + 1
    topic.question_count = len(topic.items)
    return topic, None


_cache: dict[str, Any] = {"stamp": None, "catalog": None}


def _dir_stamp(root: Path) -> tuple:
    if not root.is_dir():
        return ()
    return tuple(
        sorted((p.as_posix(), p.stat().st_mtime_ns) for p in root.rglob("*.json") if p.is_file())
    )


def load_catalog(*, root: Path | None = None, refresh: bool = False) -> Catalog:
    """Walk ``data/questions/**``. Cached until a file's mtime or the file set changes."""
    base = Path(root) if root else QUESTIONS_DIR
    stamp = (base.as_posix(), _dir_stamp(base))
    if not refresh and _cache["stamp"] == stamp and _cache["catalog"] is not None:
        return _cache["catalog"]

    catalog = Catalog()
    if base.is_dir():
        for kind in CONTENT_KINDS:
            kind_dir = base / kind
            if not kind_dir.is_dir():
                continue
            for path in sorted(kind_dir.rglob("*.json")):
                if not path.is_file() or path.name.startswith("."):
                    continue
                # Meta / roadmap files live beside content (e.g. math/curriculum.json).
                # `_user` is the Study Loop CRUD pack folder and must be loaded.
                rel_parts = path.relative_to(kind_dir).parts
                if path.name in {"curriculum.json"}:
                    continue
                if any(part.startswith("_") and part != "_user" for part in rel_parts):
                    continue
                topic, err = _read_file(path, base)
                if err:
                    catalog.errors.append(err)
                    continue
                assert topic is not None
                if topic.kind != kind:
                    catalog.errors.append(
                        {
                            "file": topic.source_file,
                            "error": f"kind '{topic.kind}' does not match folder '{kind}'",
                        }
                    )
                    continue
                if catalog.by_id(topic.topic_id):
                    catalog.errors.append(
                        {"file": topic.source_file, "error": f"duplicate topic_id {topic.topic_id}"}
                    )
                    continue
                catalog.topics.append(topic)

    catalog.topics.sort(key=lambda t: (t.kind, t.stage, t.topic_id))
    _cache["stamp"] = stamp
    _cache["catalog"] = catalog
    return catalog


def list_topics(
    *,
    kind: str | None = None,
    track: str | None = None,
    note_topic_id: str | None = None,
    root: Path | None = None,
) -> list[TopicEntry]:
    catalog = load_catalog(root=root)
    want_kind = normalize_kind(kind) if kind else None
    tag = (note_topic_id or "").strip().upper()
    out = []
    for topic in catalog.topics:
        if want_kind and topic.kind != want_kind:
            continue
        if track and topic.track.lower() != track.strip().lower():
            continue
        if tag and tag not in topic.note_topic_ids:
            continue
        out.append(topic)
    return out


def get_questions(
    *,
    topic_id: str | None = None,
    kind: str | None = None,
    difficulty: str | None = None,
    note_topic_id: str | None = None,
    question_ids: list[str] | None = None,
    root: Path | None = None,
) -> list[dict[str, Any]]:
    """Normalized quiz items matching the filters, in authored order."""
    catalog = load_catalog(root=root)
    wanted_ids = {str(i) for i in (question_ids or [])}
    topics = (
        [t for t in [catalog.by_id(topic_id)] if t]
        if topic_id
        else list_topics(kind=kind, note_topic_id=note_topic_id, root=root)
    )
    items: list[dict[str, Any]] = []
    for topic in topics:
        if kind and topic.kind != normalize_kind(kind):
            continue
        for item in topic.items:
            if wanted_ids and item["id"] not in wanted_ids:
                continue
            if difficulty and item.get("difficulty") != difficulty.strip().lower():
                continue
            items.append(dict(item))
    return items


def build_quiz_items(
    *,
    kind: str | None = None,
    topic_id: str | None = None,
    count: int | None = None,
    difficulty: str | None = None,
    note_topic_id: str | None = None,
    question_ids: list[str] | None = None,
    shuffle: bool = False,
    root: Path | None = None,
) -> list[dict[str, Any]]:
    """Items ready for ``handler.start_session`` payloads."""
    items = get_questions(
        topic_id=topic_id,
        kind=kind,
        difficulty=difficulty,
        note_topic_id=note_topic_id,
        question_ids=question_ids,
        root=root,
    )
    if shuffle:
        items = random.sample(items, k=len(items))
    if count and count > 0:
        items = items[: int(count)]
    return items


def content_items_to_math_in(*, kind: str | None = "math") -> list[Any]:
    """Convert curated content-bank quiz items into MathQuestionIn rows for SQLite."""
    from backend.math.schemas import MathQuestionIn

    catalog = load_catalog()
    items = get_questions(kind=kind)
    out: list[MathQuestionIn] = []
    for it in items:
        topic_id = str(it.get("topic_id") or it.get("topic") or "math.unknown")
        prompt = str(it.get("prompt") or "").strip()
        answer = str(it.get("expected_answer") or it.get("answer") or "").strip()
        if not prompt:
            continue
        fmt = str(it.get("answer_format") or ("open" if not answer else "expression"))
        tags = list(it.get("tags") or [])
        if not answer and "no-answer" not in tags:
            tags.append("no-answer")
        meta: dict[str, Any] = {
            "topic_id": topic_id,
            "topic_title": it.get("topic_title"),
            "content_kind": it.get("content_kind") or it.get("kind"),
            "open": not bool(answer),
        }
        topic = catalog.by_id(topic_id)
        if topic and topic.note_topic_ids:
            meta["note_topic_ids"] = list(topic.note_topic_ids)
            for n in topic.note_topic_ids:
                if n not in tags:
                    tags.append(n)
        out.append(
            MathQuestionIn(
                topic=topic_id[:80],
                prompt=prompt[:1000],
                expected_answer=answer[:500],
                explanation=(it.get("explanation") or None),
                difficulty=(it.get("difficulty") or None),
                answer_format=fmt,
                tags=tags,
                external_id=str(it.get("id") or "")[:80] or None,
                source="content_bank",
                metadata=meta,
            )
        )
    return out


def sync_curated_to_db(db: Any, *, kind: str | None = "math") -> dict[str, Any]:
    from backend.math.services.import_questions import upsert_questions

    rows = content_items_to_math_in(kind=kind)
    result = upsert_questions(db, rows, default_source="content_bank")
    return result.model_dump()


def import_content(
    db: Any,
    *,
    user_id: int,
    kind: str | None = None,
    topic_id: str | None = None,
    root: Path | None = None,
) -> dict[str, Any]:
    """Seed FSRS review cards for authored content, grouped by ``topic_id``."""
    from backend.quiz import review_cards as rc_mod

    topics = (
        [t for t in [load_catalog(root=root).by_id(topic_id)] if t]
        if topic_id
        else list_topics(kind=kind, root=root)
    )
    seeded = 0
    for topic in topics:
        domain = {
            "coding": "code",
            "math": "math",
            "mcq": "study",
            "coding_mcq": "study",
        }.get(topic.kind, "study")
        seeded += rc_mod.seed_content_cards(
            db,
            user_id=user_id,
            domain=domain,
            topic_id=topic.topic_id,
            topic_title=topic.title,
            items=topic.items,
        )
    catalog = load_catalog(root=root)
    return {
        "topics": len(topics),
        "cards_seeded": seeded,
        "questions": sum(t.question_count for t in topics),
        "errors": catalog.errors,
    }


def _cli() -> int:
    catalog = load_catalog(refresh=True)
    for topic in catalog.topics:
        print(f"ok    {topic.kind:6} {topic.topic_id:44} {topic.question_count:3} q  {topic.source_file}")
    for err in catalog.errors:
        print(f"FAIL  {err['file']}: {err['error']}")
    print(
        f"\n{len(catalog.topics)} topic(s), "
        f"{sum(t.question_count for t in catalog.topics)} question(s), "
        f"{len(catalog.errors)} error(s) under {QUESTIONS_DIR}"
    )
    return 1 if catalog.errors else 0


if __name__ == "__main__":  # pragma: no cover - manual validation entry point
    import sys as _sys

    raise SystemExit(_cli() if "--validate" in _sys.argv else _cli())
