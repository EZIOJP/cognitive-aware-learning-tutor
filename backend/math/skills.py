"""Math skill catalog + mastery gating (JSON seed; dynamic adaptive drills)."""

from __future__ import annotations

import json
import statistics
from collections import Counter
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

from sqlalchemy.orm import Session

from backend.models import MathAttempt

Status = Literal["locked", "available", "in_progress", "mastered"]

_SKILLS_PATH = Path(__file__).with_name("skills.json")


@lru_cache(maxsize=1)
def load_catalog() -> dict[str, Any]:
    return json.loads(_SKILLS_PATH.read_text(encoding="utf-8"))


def reload_catalog() -> dict[str, Any]:
    load_catalog.cache_clear()
    return load_catalog()


def list_nodes() -> list[dict[str, Any]]:
    return list(load_catalog().get("nodes") or [])


def get_node(node_id: str) -> dict[str, Any] | None:
    nid = (node_id or "").strip()
    for n in list_nodes():
        if str(n.get("id")) == nid:
            return n
    return None


def mastery_rule() -> tuple[int, float, int]:
    rule = load_catalog().get("mastery_rule") or {}
    return (
        int(rule.get("window") or 20),
        float(rule.get("min_accuracy") or 0.85),
        int(rule.get("max_median_ms") or 8000),
    )


def recent_attempts_for_skill(
    db: Session, *, user_id: int, skill_id: str, limit: int = 20
) -> list[MathAttempt]:
    """Attempts scoped to a skill: topic == skill_id (drill convention)."""
    return (
        db.query(MathAttempt)
        .filter(MathAttempt.user_id == user_id, MathAttempt.topic == skill_id)
        .order_by(MathAttempt.created_at.desc())
        .limit(limit)
        .all()
    )


def weak_factors_for_skill(
    db: Session, *, user_id: int, skill_id: str, limit: int = 40
) -> list[int]:
    """Numbers the user missed most often in recent wrong attempts."""
    from backend.math.generators.layer0 import parse_factors_from_prompt

    rows = (
        db.query(MathAttempt)
        .filter(
            MathAttempt.user_id == user_id,
            MathAttempt.topic == skill_id,
            MathAttempt.is_correct.is_(False),
        )
        .order_by(MathAttempt.created_at.desc())
        .limit(limit)
        .all()
    )
    counts: Counter[int] = Counter()
    for r in rows:
        for f in parse_factors_from_prompt(str(r.prompt or "")):
            if 2 <= f <= 100:
                counts[f] += 1
    return [n for n, _ in counts.most_common(8)]


def skill_speed_median_ms(db: Session, *, user_id: int, skill_id: str) -> float | None:
    """
    Median recent answer times from hub node metadata (written on submit).
    Returns None if not enough samples.
    """
    from backend.models.knowledge_graph import KgNode

    window, _, _ = mastery_rule()
    node = (
        db.query(KgNode)
        .filter(KgNode.user_id == user_id, KgNode.label == skill_id)
        .first()
    )
    if not node or not node.metadata_json:
        return None
    try:
        meta = json.loads(node.metadata_json)
    except json.JSONDecodeError:
        return None
    samples = meta.get("recent_ms") or []
    if not isinstance(samples, list) or len(samples) < max(5, window // 4):
        return None
    nums = [float(x) for x in samples if isinstance(x, (int, float))]
    if len(nums) < 5:
        return None
    return float(statistics.median(nums[-window:]))


def record_skill_timing(
    db: Session, *, user_id: int, skill_id: str, time_taken_ms: int, correct: bool
) -> None:
    """Append latency sample onto math_topic hub node for speed mastery."""
    from backend.hub.services.knowledge_graph import upsert_node

    if time_taken_ms <= 0:
        return
    node = upsert_node(db, user_id=user_id, label=skill_id, node_type="math_topic")
    meta = json.loads(node.metadata_json or "{}") if node.metadata_json else {}
    recent = list(meta.get("recent_ms") or [])
    # Weight correct answers more for unlock; still record misses as slower practice
    recent.append(int(time_taken_ms) if correct else int(time_taken_ms * 1.15))
    meta["recent_ms"] = recent[-40:]
    # Weak-factor bag for UI / daily mix
    weak = list(meta.get("weak_factors") or [])
    meta["weak_factors"] = weak
    node.metadata_json = json.dumps(meta)
    db.commit()


def update_weak_factors_meta(
    db: Session, *, user_id: int, skill_id: str, factors: list[int], correct: bool
) -> None:
    if correct or not factors:
        return
    from backend.hub.services.knowledge_graph import upsert_node

    node = upsert_node(db, user_id=user_id, label=skill_id, node_type="math_topic")
    meta = json.loads(node.metadata_json or "{}") if node.metadata_json else {}
    bag = list(meta.get("weak_factors") or [])
    bag.extend(int(f) for f in factors if 2 <= int(f) <= 100)
    meta["weak_factors"] = bag[-60:]
    node.metadata_json = json.dumps(meta)
    db.commit()


def is_mastered(db: Session, *, user_id: int, skill_id: str, require_speed: bool = False) -> bool:
    window, min_acc, max_median_ms = mastery_rule()
    rows = recent_attempts_for_skill(db, user_id=user_id, skill_id=skill_id, limit=window)
    if len(rows) < window:
        return False
    correct = sum(1 for r in rows if r.is_correct)
    if (correct / window) < min_acc:
        return False
    if require_speed:
        med = skill_speed_median_ms(db, user_id=user_id, skill_id=skill_id)
        if med is None or med > max_median_ms:
            return False
    return True


def node_status(db: Session, *, user_id: int, node: dict[str, Any]) -> Status:
    skill_id = str(node["id"])
    need_speed = bool(node.get("require_speed"))
    if is_mastered(db, user_id=user_id, skill_id=skill_id, require_speed=need_speed):
        return "mastered"
    for pre in node.get("prereqs") or []:
        pre_node = get_node(str(pre))
        pre_speed = bool(pre_node.get("require_speed")) if pre_node else False
        if not is_mastered(db, user_id=user_id, skill_id=str(pre), require_speed=pre_speed):
            return "locked"
    rows = recent_attempts_for_skill(db, user_id=user_id, skill_id=skill_id, limit=1)
    return "in_progress" if rows else "available"


def list_nodes_with_status(db: Session, *, user_id: int) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    window, min_acc, max_median_ms = mastery_rule()
    for n in list_nodes():
        st = node_status(db, user_id=user_id, node=n)
        rows = recent_attempts_for_skill(db, user_id=user_id, skill_id=str(n["id"]), limit=window)
        correct = sum(1 for r in rows if r.is_correct)
        med = skill_speed_median_ms(db, user_id=user_id, skill_id=str(n["id"]))
        out.append(
            {
                **n,
                "status": st,
                "progress": {
                    "attempts": len(rows),
                    "correct": correct,
                    "window": window,
                    "min_accuracy": min_acc,
                    "max_median_ms": max_median_ms,
                    "median_ms": med,
                    "require_speed": bool(n.get("require_speed")),
                },
            }
        )
    return out


def next_available_node(db: Session, *, user_id: int) -> dict[str, Any] | None:
    """Lowest-layer in_progress, else lowest-layer available (skip daily_mixed as default)."""
    ranked = list_nodes_with_status(db, user_id=user_id)
    ranked = [n for n in ranked if str(n["id"]) != "daily_mixed_5"]
    in_prog = [n for n in ranked if n["status"] == "in_progress"]
    if in_prog:
        in_prog.sort(key=lambda n: (int(n.get("layer") or 0), str(n["id"])))
        return in_prog[0]
    avail = [n for n in ranked if n["status"] == "available"]
    if not avail:
        return None
    avail.sort(key=lambda n: (int(n.get("layer") or 0), str(n["id"])))
    return avail[0]


def generate_drill_items(
    node_id: str,
    n: int = 5,
    *,
    db: Session | None = None,
    user_id: int | None = None,
) -> list[dict[str, Any]]:
    from backend.math.generators.layer0 import generate_for_node

    node = get_node(node_id)
    if not node:
        raise ValueError(f"Unknown skill node: {node_id}")
    n = max(1, min(int(n or 5), 50))
    bias: list[int] = []
    if db is not None and user_id is not None:
        bias = weak_factors_for_skill(db, user_id=user_id, skill_id=node_id)

    items: list[dict[str, Any]] = []
    for i in range(n):
        # Daily pack: force variety across modes
        if node_id == "daily_mixed_5":
            from backend.math.generators import layer0 as L

            pickers = [
                lambda: L.gen_times_tables(
                    node_id,
                    "Arithmetic",
                    {
                        "a_min": 3,
                        "a_max": 20,
                        "b_min": 3,
                        "b_max": 20,
                        "exclude_factors": [1, 2, 10],
                    },
                    bias_factors=bias,
                ),
                lambda: L.gen_powers(
                    node_id,
                    "Arithmetic",
                    {"exponent": 2, "base_min": 2, "base_max": 30, "exclude_factors": [1]},
                    bias_factors=bias,
                ),
                lambda: L.gen_times_reverse(
                    node_id,
                    "Arithmetic",
                    {
                        "a_min": 3,
                        "a_max": 12,
                        "b_min": 3,
                        "b_max": 12,
                        "exclude_factors": [1, 2, 10],
                    },
                    bias_factors=bias,
                ),
                lambda: L.gen_mental_shortcuts(
                    node_id,
                    "Arithmetic",
                    {"exclude_factors": [1, 2, 10]},
                    bias_factors=bias,
                ),
                lambda: L.gen_times_fact_family(
                    node_id,
                    "Arithmetic",
                    {"exclude_factors": [1, 2, 10]},
                    bias_factors=bias,
                ),
            ]
            p = pickers[i % len(pickers)]()
        else:
            p = generate_for_node(node, bias_factors=bias or None)
        items.append(
            {
                "kind": "math",
                "id": p.get("generated_id") or f"{node_id}-{i}",
                "prompt": p["prompt"],
                "expected_answer": p["expected_answer"],
                "topic": node_id,
                "hint": p.get("explanation"),
                "question_id": None,
                "generated_id": p.get("generated_id"),
                "skill_id": node_id,
                "parent_topic": node.get("topic") or "Arithmetic",
                "factors": p.get("factors") or [],
                "mode": p.get("mode") or "",
            }
        )
    return items
