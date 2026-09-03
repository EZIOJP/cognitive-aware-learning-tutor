from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any

from backend.math.curriculum_pass.curriculum import normalize_topic_id
from backend.math.curriculum_pass.topic_ids import canonicalize_topic_id


@dataclass
class MapResult:
    status: str  # mapped | quarantined
    pack: dict[str, Any]
    multi_topic: bool = False
    removed_note_topic_ids: list[str] = field(default_factory=list)


def map_pack(
    pack: dict[str, Any],
    reverse_index: dict[str, set[str]],
    curriculum_mts: set[str],
) -> MapResult:
    topic = dict((pack.get("topic") or {}))
    topic_id = str(topic.get("topic_id") or "")
    computed = set(reverse_index.get(normalize_topic_id(topic_id), set()))
    if not computed:
        return MapResult(status="quarantined", pack=pack, multi_topic=False)

    existing_raw = list(topic.get("note_topic_ids") or [])
    valid_existing: list[str] = []
    removed: list[str] = []
    for raw in existing_raw:
        canon = canonicalize_topic_id(str(raw)) or str(raw).strip()
        if canon in curriculum_mts:
            if canon not in valid_existing:
                valid_existing.append(canon)
        else:
            removed.append(str(raw))

    union = sorted(set(valid_existing) | computed)
    out = deepcopy(pack)
    out_topic = dict(out.get("topic") or {})
    out_topic["note_topic_ids"] = union
    out["topic"] = out_topic

    questions = []
    for q in out.get("questions") or []:
        qq = dict(q)
        tags = [str(t) for t in (qq.get("tags") or [])]
        for mt in union:
            if mt not in tags:
                tags.append(mt)
        qq["tags"] = tags
        questions.append(qq)
    out["questions"] = questions

    return MapResult(
        status="mapped",
        pack=out,
        multi_topic=len(computed) > 1,
        removed_note_topic_ids=removed,
    )
