from __future__ import annotations

import json
from pathlib import Path

from backend.math.curriculum_pass.constants import CURRICULUM_PATH
from backend.math.curriculum_pass.topic_ids import canonicalize_topic_id


def normalize_topic_id(raw: str) -> str:
    return (raw or "").strip().lower()


def load_curriculum(path: Path | None = None) -> dict:
    p = path or CURRICULUM_PATH
    return json.loads(p.read_text(encoding="utf-8"))


def build_reverse_index(curriculum: dict) -> dict[str, set[str]]:
    out: dict[str, set[str]] = {}
    for level in curriculum.get("levels") or []:
        for step in level.get("steps") or []:
            mt = canonicalize_topic_id(str(step.get("note_topic_id") or "")) or str(
                step.get("note_topic_id") or ""
            ).strip()
            if not mt:
                continue
            for tid in step.get("prefer_topic_ids") or []:
                key = normalize_topic_id(str(tid))
                if not key:
                    continue
                out.setdefault(key, set()).add(mt)
    return out


def all_curriculum_mt_ids(curriculum: dict) -> list[tuple[str, str]]:
    seen: set[str] = set()
    rows: list[tuple[str, str]] = []
    for level in curriculum.get("levels") or []:
        for step in level.get("steps") or []:
            mt = canonicalize_topic_id(str(step.get("note_topic_id") or "")) or ""
            title = str(step.get("title") or mt).strip()
            if mt and mt not in seen:
                seen.add(mt)
                rows.append((mt, title))
    return rows
