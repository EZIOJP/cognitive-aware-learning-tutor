"""Study Loop tag index — list / add / rename / merge across notes, questions, vocab.

Approach A: rename/merge rewrite on-disk ``data/questions/**/*.json`` (not index-only).
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from backend import paths
from backend.quiz.atomic_io import atomic_write_text
from backend.quiz.content_bank import load_catalog
from backend.quiz.read_cards import list_read_cards
from backend.quiz.source_stamp import bump_notes, bump_questions
from backend.transcripts.note_topics import canonicalize_topic_id

NOTES_DIR: Path = paths.NOTES_DIR
QUESTIONS_DIR: Path = paths.QUESTIONS_DIR
WORDS_PATH: Path = paths.WORDS_PATH

_NOTE_TOPIC_RE = re.compile(r"^(?:L|MT)\d+-T\d+$", re.IGNORECASE)
_FREE_TAG_RE = re.compile(r"^[a-z0-9][a-z0-9._-]*$")
_VOCAB_GROUP_RE = re.compile(r"^vocab\.group\.(\d+)$", re.IGNORECASE)


def is_note_topic(tag: str) -> bool:
    raw = (tag or "").strip()
    if not raw:
        return False
    canon = canonicalize_topic_id(raw) or raw.upper()
    return bool(_NOTE_TOPIC_RE.match(canon))


def _canon_note(tag: str) -> str:
    return canonicalize_topic_id(tag) or tag.strip().upper()


def _norm_id(tag: str) -> str:
    raw = (tag or "").strip()
    if not raw:
        return ""
    if _VOCAB_GROUP_RE.match(raw):
        m = _VOCAB_GROUP_RE.match(raw)
        assert m is not None
        return f"vocab.group.{int(m.group(1))}"
    if is_note_topic(raw):
        return _canon_note(raw)
    return raw.lower()


def _tag_kind(tag_id: str) -> str:
    if tag_id.startswith("vocab.group."):
        return "vocab_group"
    if is_note_topic(tag_id):
        return "note_topic"
    return "free"


def _tags_equal(a: str, b: str) -> bool:
    if is_note_topic(a) or is_note_topic(b):
        return _canon_note(a) == _canon_note(b)
    return a.strip().lower() == b.strip().lower()


def _replace_tag_value(value: str, old: str, new: str) -> str:
    if _tags_equal(value, old):
        if is_note_topic(new):
            return _canon_note(new)
        if _VOCAB_GROUP_RE.match(new.strip()):
            return _norm_id(new)
        return new.strip().lower() if _FREE_TAG_RE.match(new.strip().lower()) else new.strip()
    return value


def _replace_in_str_list(items: list[Any], old: str, new: str) -> tuple[list[Any], bool]:
    out: list[Any] = []
    changed = False
    seen: set[str] = set()
    new_norm = _norm_id(new) if new else ""
    for raw in items:
        s = str(raw)
        if _tags_equal(s, old):
            changed = True
            if not new_norm:
                continue
            key = new_norm.lower()
            if key in seen:
                continue
            seen.add(key)
            out.append(_replace_tag_value(s, old, new))
        else:
            key = s.strip().lower()
            if key in seen:
                continue
            seen.add(key)
            out.append(raw)
    return out, changed


def load_words(db: Any = None) -> list[dict[str, Any]]:
    """Load vocab words; monkeypatchable entry point for tests."""
    try:
        from backend.vocab.words import load_words as vocab_load_words

        return list(vocab_load_words(db))
    except Exception:
        try:
            from backend.vocab.repository import list_words_from_json_file

            return list_words_from_json_file()
        except Exception:
            return []


def save_words(words: list[dict[str, Any]], db: Any = None) -> None:
    """Persist vocab words; monkeypatchable entry point for tests."""
    from backend.vocab.words import save_words as vocab_save_words

    vocab_save_words(words, db)


def _load_vocab_words() -> list[dict[str, Any]]:
    return load_words()


def _save_vocab_words(words: list[dict[str, Any]]) -> None:
    save_words(words)


def _iter_question_json_files(root: Path) -> list[Path]:
    if not root.is_dir():
        return []
    out: list[Path] = []
    for path in sorted(root.rglob("*.json")):
        if not path.is_file() or path.name.startswith("."):
            continue
        out.append(path)
    return out


def _rewrite_question_payload(data: dict[str, Any], old: str, new: str) -> bool:
    changed = False
    topic = data.get("topic")
    if isinstance(topic, dict):
        nids = topic.get("note_topic_ids")
        if isinstance(nids, list):
            replaced, did = _replace_in_str_list(nids, old, new)
            if did:
                topic["note_topic_ids"] = replaced
                changed = True
        # curriculum-style nested steps may live outside ContentFile
    # curriculum.json levels/steps
    levels = data.get("levels")
    if isinstance(levels, list):
        for level in levels:
            if not isinstance(level, dict):
                continue
            steps = level.get("steps")
            if not isinstance(steps, list):
                continue
            for step in steps:
                if not isinstance(step, dict):
                    continue
                ntid = step.get("note_topic_id")
                if isinstance(ntid, str) and _tags_equal(ntid, old):
                    step["note_topic_id"] = _replace_tag_value(ntid, old, new)
                    changed = True
    questions = data.get("questions")
    if isinstance(questions, list):
        for q in questions:
            if not isinstance(q, dict):
                continue
            tags = q.get("tags")
            if isinstance(tags, list):
                replaced, did = _replace_in_str_list(tags, old, new)
                if did:
                    q["tags"] = replaced
                    changed = True
    return changed


def _rewrite_questions_on_disk(old: str, new: str) -> int:
    """Rewrite matching question JSON files. Returns number of files updated."""
    updated = 0
    for path in _iter_question_json_files(QUESTIONS_DIR):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(data, dict):
            continue
        if not _rewrite_question_payload(data, old, new):
            continue
        atomic_write_text(path, json.dumps(data, indent=2, ensure_ascii=False) + "\n")
        updated += 1
    if updated:
        bump_questions()
        load_catalog(root=QUESTIONS_DIR, refresh=True)
    return updated


def _rewrite_notes_topic_id(old: str, new: str) -> int:
    """Rewrite note heading / index refs for a note-topic rename. Returns notes touched."""
    if not is_note_topic(old) or not is_note_topic(new):
        return 0
    old_c = _canon_note(old)
    new_c = _canon_note(new)
    if old_c == new_c:
        return 0
    cards = list_read_cards(tag=old_c, root=NOTES_DIR)
    touched_paths: set[str] = set()
    pattern = re.compile(re.escape(old_c), re.IGNORECASE)
    for card in cards:
        rel = str(card.get("note_path") or "")
        if not rel or rel in touched_paths:
            continue
        path = NOTES_DIR / rel
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8")
        updated = pattern.sub(new_c, text)
        if updated == text:
            continue
        atomic_write_text(path, updated)
        touched_paths.add(rel)
    if touched_paths:
        bump_notes()
    return len(touched_paths)


def _vocab_tags(words: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[int, int] = {}
    free: dict[str, int] = {}
    for w in words:
        gn = int(w.get("group_number") or 0)
        if gn:
            groups[gn] = groups.get(gn, 0) + 1
        for t in w.get("tags") or []:
            key = str(t).strip().lower()
            if key:
                free[key] = free.get(key, 0) + 1
    out: list[dict[str, Any]] = []
    for gn, count in sorted(groups.items()):
        out.append(
            {
                "id": f"vocab.group.{gn}",
                "kind": "vocab_group",
                "label": f"GRE group {gn}",
                "vocab_count": count,
                "question_count": 0,
                "has_read_card": False,
                "note_paths": [],
            }
        )
    for tag, count in sorted(free.items()):
        out.append(
            {
                "id": tag,
                "kind": "free",
                "label": tag,
                "vocab_count": count,
                "question_count": 0,
                "has_read_card": False,
                "note_paths": [],
            }
        )
    return out


def _rewrite_vocab_tags(old: str, new: str) -> int:
    words = _load_vocab_words()
    if not words:
        return 0
    changed_rows = 0
    for word in words:
        tags = word.get("tags")
        if not isinstance(tags, list):
            continue
        replaced, did = _replace_in_str_list(tags, old, new)
        if did:
            word["tags"] = replaced
            changed_rows += 1
    if changed_rows:
        try:
            _save_vocab_words(words)
        except Exception:
            # Best-effort when DB/session unavailable (unit tests without vocab attach).
            if WORDS_PATH.is_file():
                atomic_write_text(
                    WORDS_PATH,
                    json.dumps(words, indent=2, ensure_ascii=False) + "\n",
                )
    return changed_rows


def list_tags(*, q: str | None = None, kind: str | None = None) -> list[dict[str, Any]]:
    """Union of note topics, free question tags, and vocab group/free tags."""
    by_id: dict[str, dict[str, Any]] = {}

    def ensure(tag_id: str, *, label: str | None = None) -> dict[str, Any] | None:
        tid = _norm_id(tag_id)
        if not tid:
            return None
        entry = by_id.get(tid)
        if entry is None:
            entry = {
                "id": tid,
                "kind": _tag_kind(tid),
                "label": label or tid,
                "aliases": [],
                "note_paths": [],
                "question_count": 0,
                "vocab_count": 0,
                "has_read_card": False,
            }
            by_id[tid] = entry
        elif label and (not entry.get("has_read_card") or entry["label"] == entry["id"]):
            entry["label"] = label
        return entry

    # Notes → note_topic tags
    for card in list_read_cards(root=NOTES_DIR):
        entry = ensure(str(card.get("tag") or ""), label=str(card.get("title") or ""))
        if entry is None:
            continue
        entry["has_read_card"] = True
        if not entry["label"]:
            entry["label"] = entry["id"]
        rel = str(card.get("note_path") or "")
        if rel and rel not in entry["note_paths"]:
            entry["note_paths"].append(rel)

    # Content bank → note_topic_ids + item tags
    catalog = load_catalog(root=QUESTIONS_DIR, refresh=True)
    for topic in catalog.topics:
        for ntid in topic.note_topic_ids:
            entry = ensure(ntid, label=topic.title)
            if entry is None:
                continue
            entry["question_count"] += int(topic.question_count or 0)
        for item in topic.items:
            for raw in item.get("tags") or []:
                tag = str(raw).strip()
                if not tag:
                    continue
                entry = ensure(tag)
                if entry is None:
                    continue
                entry["question_count"] += 1

    # Vocab groups + free tags on words
    for entry in _vocab_tags(_load_vocab_words()):
        tid = str(entry.get("id") or "")
        row = ensure(tid, label=str(entry.get("label") or tid))
        if row is None:
            continue
        row["vocab_count"] += int(entry.get("vocab_count") or 0)

    want_kind = (kind or "").strip().lower() or None
    needle = (q or "").strip().lower() or None
    out: list[dict[str, Any]] = []
    for entry in by_id.values():
        if want_kind and entry["kind"] != want_kind:
            continue
        if needle and needle not in entry["id"].lower() and needle not in str(entry["label"]).lower():
            continue
        out.append(entry)
    out.sort(key=lambda e: (e["kind"], e["id"]))
    return out


def add_tag(
    tag_id: str,
    *,
    question_id: str | None = None,
    word_ids: list[int] | None = None,
    note_path: str | None = None,
    topic_id: str | None = None,
) -> dict[str, Any]:
    tid = _norm_id(tag_id)
    if not tid:
        raise ValueError("tag id required")
    refs = 0

    if question_id:
        qid = question_id.strip()
        found = False
        for path in _iter_question_json_files(QUESTIONS_DIR):
            if path.name == "curriculum.json":
                continue
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if not isinstance(data, dict):
                continue
            questions = data.get("questions")
            if not isinstance(questions, list):
                continue
            changed = False
            for q in questions:
                if not isinstance(q, dict) or str(q.get("id")) != qid:
                    continue
                tags = list(q.get("tags") or [])
                if not any(_tags_equal(str(t), tid) for t in tags):
                    tags.append(tid if not is_note_topic(tid) else _canon_note(tid))
                    q["tags"] = tags
                    changed = True
                found = True
                break
            if changed:
                atomic_write_text(path, json.dumps(data, indent=2, ensure_ascii=False) + "\n")
                refs += 1
                bump_questions()
                load_catalog(root=QUESTIONS_DIR, refresh=True)
                break
        if not found:
            raise ValueError(f"question not found: {qid}")

    if word_ids:
        want = {int(x) for x in word_ids}
        words = _load_vocab_words()
        for word in words:
            wid = word.get("id")
            if wid is None or int(wid) not in want:
                continue
            tags = list(word.get("tags") or [])
            if not any(_tags_equal(str(t), tid) for t in tags):
                tags.append(tid)
                word["tags"] = tags
                refs += 1
        if refs:
            _save_vocab_words(words)

    if note_path and topic_id:
        # Free-tag footer under section; note-topic section creation is out of scope.
        if is_note_topic(tid):
            raise ValueError("creating note_topic sections via add_tag is out of scope")
        base = NOTES_DIR
        rel = note_path.replace("\\", "/").lstrip("/")
        path = (base / rel).resolve()
        if not path.is_relative_to(base.resolve()) or not path.is_file():
            raise ValueError("invalid note_path")
        section = _canon_note(topic_id)
        text = path.read_text(encoding="utf-8")
        marker = f"<!-- tags:"
        # Insert after the matching heading line if not already present nearby.
        lines = text.splitlines(keepends=True)
        inserted = False
        for i, line in enumerate(lines):
            if section.lower() in line.lower().replace("`", "") and line.lstrip().startswith("#"):
                # Check next few lines for existing tags comment
                window = "".join(lines[i : i + 4])
                if tid.lower() in window.lower() and "tags:" in window.lower():
                    inserted = True
                    break
                inject = f"<!-- tags: {tid} -->\n"
                lines.insert(i + 1, inject)
                inserted = True
                refs += 1
                break
        if not inserted:
            raise ValueError(f"section {section} not found in {rel}")
        if refs:
            atomic_write_text(path, "".join(lines))
            bump_notes()

    tags = {t["id"]: t for t in list_tags()}
    if tid not in tags:
        # Brand-new free tag with no attach yet
        return {
            "id": tid,
            "kind": _tag_kind(tid),
            "label": tid,
            "aliases": [],
            "note_paths": [],
            "question_count": 0,
            "vocab_count": 0,
            "has_read_card": False,
            "refs_updated": refs,
        }
    out = dict(tags[tid])
    out["refs_updated"] = refs
    return out


def rename_tag(old: str, new: str) -> dict[str, Any]:
    old_id = (old or "").strip()
    new_id = (new or "").strip()
    if not old_id or not new_id:
        raise ValueError("old and new tag ids required")
    if _tags_equal(old_id, new_id):
        return {"renamed": True, "refs_updated": 0, "old_id": _norm_id(old_id), "new_id": _norm_id(new_id)}

    refs = 0
    refs += _rewrite_questions_on_disk(old_id, new_id)
    refs += _rewrite_notes_topic_id(old_id, new_id)
    refs += _rewrite_vocab_tags(old_id, new_id)
    return {
        "renamed": True,
        "refs_updated": refs,
        "old_id": _norm_id(old_id),
        "new_id": _norm_id(new_id),
    }


def merge_tags(from_tag: str, into_tag: str) -> dict[str, Any]:
    src = (from_tag or "").strip()
    dst = (into_tag or "").strip()
    if not src or not dst:
        raise ValueError("from_tag and into_tag required")
    if is_note_topic(src) and is_note_topic(dst):
        raise ValueError("cannot_merge_note_topics")
    if _tags_equal(src, dst):
        return {"merged": True, "refs_updated": 0, "from_tag": _norm_id(src), "into_tag": _norm_id(dst)}

    refs = 0
    refs += _rewrite_questions_on_disk(src, dst)
    # Merging a note_topic into a free/vocab tag: rewrite note headings to destination only when dst is note.
    if is_note_topic(src) and is_note_topic(dst):
        pass  # unreachable — rejected above
    elif is_note_topic(src):
        # Drop heading ids? Leave notes for manual edit (design: merging two note topics is manual).
        # When merging note → free, still rewrite JSON; notes left alone.
        pass
    refs += _rewrite_vocab_tags(src, dst)
    return {
        "merged": True,
        "refs_updated": refs,
        "from_tag": _norm_id(src),
        "into_tag": _norm_id(dst),
    }
