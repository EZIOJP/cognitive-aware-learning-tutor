from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from backend import paths
from backend.transcripts.note_topics import canonicalize_topic_id, parse_note_topics

logger = logging.getLogger(__name__)

# URL-safe separator (never use "#" — browsers treat it as a fragment).
CARD_ID_SEP = "::"


def make_card_id(note_path: str, topic_id: str) -> str:
    rel = Path(str(note_path).replace("\\", "/")).as_posix().lstrip("/")
    tid = canonicalize_topic_id(topic_id) or topic_id.strip().upper()
    return f"{rel}{CARD_ID_SEP}{tid}"


def parse_card_id(card_id: str) -> tuple[str, str]:
    raw = Path(str(card_id or "").replace("\\", "/")).as_posix()
    # Accept legacy "#" only if somehow still present; prefer "::".
    if CARD_ID_SEP in raw:
        path, tag = raw.rsplit(CARD_ID_SEP, 1)
    elif "#" in raw:
        path, tag = raw.rsplit("#", 1)
    else:
        raise ValueError("card_id must look like path::TOPIC")
    if not path or not tag.strip():
        raise ValueError("card_id must look like path::TOPIC")
    tid = canonicalize_topic_id(tag) or tag.strip().upper()
    return path, tid


def _iter_note_files(root: Path) -> list[Path]:
    if not root.is_dir():
        return []
    out: list[Path] = []
    for p in sorted(root.rglob("*.md")):
        if not p.is_file():
            continue
        rel = p.relative_to(root).as_posix()
        if rel.startswith("rules/") or "/rules/" in f"/{rel}":
            continue
        out.append(p)
    return out


def list_read_cards(*, tag: str | None = None, root: Path | None = None) -> list[dict[str, Any]]:
    base = Path(root) if root else paths.NOTES_DIR
    want = None
    if tag:
        want = canonicalize_topic_id(tag) or tag.strip().upper()
    cards: list[dict[str, Any]] = []
    for path in _iter_note_files(base):
        rel = path.relative_to(base).as_posix()
        try:
            text = path.read_text(encoding="utf-8")
            mtime = path.stat().st_mtime
            topics = parse_note_topics(text, min_body_chars=1, max_topics=80)
        except Exception as exc:  # noqa: BLE001 — one bad file must not 500 the Loop tab
            logger.warning("read_cards: skip %s (%s)", rel, exc)
            continue
        for topic in topics:
            try:
                tid = canonicalize_topic_id(topic.topic_id) or topic.topic_id
                if want and tid.upper() != want.upper():
                    continue
                heading = ""
                for line in text.splitlines():
                    if tid.upper() in line.upper() and line.lstrip().startswith("#"):
                        heading = line
                        break
                cards.append(
                    {
                        "card_id": make_card_id(rel, tid),
                        "tag": tid,
                        "title": topic.title,
                        "body_markdown": topic.body,
                        "heading_markdown": heading,
                        "note_path": rel,
                        "mtime": mtime,
                        "source": topic.source,
                        "char_count": len(topic.body),
                    }
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning("read_cards: skip topic in %s (%s)", rel, exc)
                continue
    return cards


def get_read_card(card_id: str, *, root: Path | None = None) -> dict[str, Any] | None:
    try:
        path, tid = parse_card_id(card_id)
    except ValueError:
        return None
    path = Path(path.replace("\\", "/")).as_posix()
    for card in list_read_cards(tag=tid, root=root):
        if card["note_path"] == path and card["tag"].upper() == tid.upper():
            return card
    return None
