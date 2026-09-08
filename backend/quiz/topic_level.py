"""Per-tag difficulty ladder: easy → medium → hard → advanced.

Study Loop / daily math practice serves only the user's current unlocked level
for that note topic. Passing a session (≥ PASS_ACCURACY) unlocks the next level
that still has inventory. Generators count as easy fluency only.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from backend.paths import ROOT
from backend.quiz.atomic_io import atomic_write_text
from backend.quiz.importance import _file_lock

STORE_PATH = ROOT / "data" / "quiz" / "topic_difficulty.json"

LEVELS: tuple[str, ...] = ("easy", "medium", "hard", "advanced")
PASS_ACCURACY = 0.8
# Prefer curriculum easy packs when at easy (avoids olympiad tagged on same MT).
CURRICULUM_PATH = ROOT / "data" / "questions" / "math" / "curriculum.json"


def empty_store() -> dict[str, Any]:
    return {"schema_version": 1, "users": {}}


def load_store(path: Path | None = None) -> dict[str, Any]:
    p = path or STORE_PATH
    if not p.is_file():
        return empty_store()
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return empty_store()
    if not isinstance(data, dict):
        return empty_store()
    data.setdefault("schema_version", 1)
    data.setdefault("users", {})
    return data


def _save(store: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_text(path, json.dumps(store, indent=2, ensure_ascii=False) + "\n")


def normalize_level(raw: str | None) -> str:
    t = (raw or "").strip().lower()
    if t in ("difficult", "diff", "challenge"):
        return "hard"
    if t in LEVELS:
        return t
    return "easy"


def next_level(level: str) -> str | None:
    cur = normalize_level(level)
    try:
        i = LEVELS.index(cur)
    except ValueError:
        return "medium"
    if i + 1 >= len(LEVELS):
        return None
    return LEVELS[i + 1]


def classify_item(item: dict[str, Any]) -> str:
    """Map a bank/generator item onto the ladder."""
    tid = str(item.get("topic_id") or item.get("topic") or "").lower()
    tags = " ".join(str(t).lower() for t in (item.get("tags") or []))
    path_s = " ".join(str(p).lower() for p in (item.get("topic_path") or []))
    blob = f"{tid} {tags} {path_s}"

    if "olympiad" in blob or "mathnet" in blob:
        return "advanced"
    if "competition" in blob or "hendrycks" in blob:
        return "hard"

    d = normalize_level(str(item.get("difficulty") or ""))
    if str(item.get("difficulty") or "").strip() and d in LEVELS:
        # Authored difficulty wins unless pack is olympiad/competition (above).
        return d

    if (
        tid.startswith("math.gen.")
        or "math.aptitude." in tid
        or "deepmind" in blob
        or "generated" in blob
        or item.get("_from_generator")
        or item.get("generator")
    ):
        return "easy"
    if "sat" in blob or "mathqa" in blob or "saket" in blob:
        return "medium"
    return "easy"


def curriculum_prefer_ids(note_topic_id: str, *, level: str = "easy") -> list[str]:
    """Preferred pack ids for a note topic at the given ladder level.

    Easy uses the first non-optional curriculum step and drops competition/olympiad.
    Harder levels may include stretch / optional steps.
    """
    tid = (note_topic_id or "").strip().upper()
    if not tid or not CURRICULUM_PATH.is_file():
        return []
    try:
        data = json.loads(CURRICULUM_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    lvl = normalize_level(level)
    out: list[str] = []
    for level_block in data.get("levels") or []:
        for step in level_block.get("steps") or []:
            if str(step.get("note_topic_id") or "").strip().upper() != tid:
                continue
            optional = bool(step.get("optional"))
            if lvl == "easy" and optional:
                continue
            if lvl in ("easy", "medium") and optional:
                # Stretch steps are hard/advanced packs.
                continue
            for p in step.get("prefer_topic_ids") or []:
                s = str(p).strip()
                if not s or s in out:
                    continue
                low = s.lower()
                if lvl == "easy" and ("competition" in low or "olympiad" in low):
                    continue
                if lvl == "medium" and ("olympiad" in low or "competition" in low):
                    continue
                if lvl == "hard" and "olympiad" in low:
                    continue
                out.append(s)
    return out


def get_stored_level(user_id: int, tag: str, *, path: Path | None = None) -> str:
    store = load_store(path)
    row = ((store.get("users") or {}).get(str(int(user_id))) or {}).get((tag or "").strip().upper())
    if not isinstance(row, dict):
        return "easy"
    return normalize_level(str(row.get("level") or "easy"))


def set_level(
    user_id: int,
    tag: str,
    level: str,
    *,
    path: Path | None = None,
    reason: str | None = None,
) -> dict[str, Any]:
    p = path or STORE_PATH
    tid = (tag or "").strip().upper()
    if not tid:
        raise ValueError("tag required")
    lvl = normalize_level(level)
    lock = p.with_suffix(p.suffix + ".lock")
    with _file_lock(lock):
        store = load_store(p)
        users = store.setdefault("users", {})
        u = users.setdefault(str(int(user_id)), {})
        now = datetime.now(UTC).isoformat().replace("+00:00", "Z")
        prev = u.get(tid) if isinstance(u.get(tid), dict) else {}
        row = {
            "level": lvl,
            "updated_at": now,
            "cleared": list(prev.get("cleared") or []),
        }
        if reason:
            row["last_reason"] = reason
        # Record prior level as cleared when moving up.
        prev_lvl = normalize_level(str(prev.get("level") or ""))
        if prev_lvl in LEVELS and LEVELS.index(prev_lvl) < LEVELS.index(lvl):
            cleared = list(row["cleared"])
            if prev_lvl not in cleared:
                cleared.append(prev_lvl)
            row["cleared"] = cleared
        u[tid] = row
        _save(store, p)
        return row


def inventory_for_tag(tag: str) -> list[dict[str, Any]]:
    from backend.quiz import content_bank as cb

    tid = (tag or "").strip()
    if not tid:
        return []
    return cb.build_quiz_items(kind="math", note_topic_id=tid, shuffle=False)


def levels_with_inventory(tag: str) -> list[str]:
    counts = {lv: 0 for lv in LEVELS}
    for it in inventory_for_tag(tag):
        lv = classify_item(it)
        counts[lv] = counts.get(lv, 0) + 1
    # Generators → easy slot even with zero bank easy.
    try:
        from backend.quiz.study_loop import math_generators_for_tag

        if math_generators_for_tag(tag):
            counts["easy"] = max(counts["easy"], 1)
    except Exception:
        pass
    return [lv for lv in LEVELS if counts.get(lv, 0) > 0]


def effective_level(user_id: int, tag: str, *, path: Path | None = None) -> str:
    """Stored level, skipped forward if that rung has no questions."""
    stored = get_stored_level(user_id, tag, path=path)
    available = levels_with_inventory(tag)
    if not available:
        return stored
    if stored in available:
        return stored
    try:
        si = LEVELS.index(stored)
    except ValueError:
        si = 0
    for lv in LEVELS[si:]:
        if lv in available:
            return lv
    return available[-1]


def filter_items_for_level(items: list[dict[str, Any]], level: str) -> list[dict[str, Any]]:
    want = normalize_level(level)
    return [it for it in items if classify_item(it) == want]


def allow_generators(level: str) -> bool:
    return normalize_level(level) == "easy"


def consider_advance(
    user_id: int,
    tag: str,
    *,
    correct: int,
    total: int,
    path: Path | None = None,
) -> dict[str, Any]:
    """Unlock next level when accuracy ≥ PASS_ACCURACY on a finished set."""
    tid = (tag or "").strip().upper()
    total_i = int(total)
    correct_i = int(correct)
    cur = effective_level(user_id, tid, path=path)
    out: dict[str, Any] = {
        "tag": tid,
        "level": cur,
        "advanced": False,
        "next_level": None,
        "accuracy": (correct_i / total_i) if total_i else 0.0,
        "pass_accuracy": PASS_ACCURACY,
    }
    if total_i <= 0 or (correct_i / total_i) < PASS_ACCURACY:
        return out
    nxt = next_level(cur)
    if not nxt:
        out["complete"] = True
        return out
    available = levels_with_inventory(tid)
    # Skip empty rungs when unlocking.
    while nxt and nxt not in available:
        nxt = next_level(nxt)
    if not nxt:
        out["complete"] = True
        return out
    set_level(user_id, tid, nxt, path=path, reason="pass")
    out["advanced"] = True
    out["next_level"] = nxt
    out["level"] = nxt
    return out


def consider_advance_from_quiz(
    db: Any,
    *,
    user_id: int,
    tag: str,
    quiz_session_id: str | None,
    path: Path | None = None,
) -> dict[str, Any]:
    if not quiz_session_id:
        return {"advanced": False, "reason": "no_quiz"}
    from backend.quiz.store import load_global_session

    sess = load_global_session(db, str(quiz_session_id), user_id)
    if not sess:
        return {"advanced": False, "reason": "session_missing"}
    attempts = sess.get("attempts") or []
    items = (sess.get("payload") or {}).get("items") or []
    if not items or len(attempts) < len(items):
        return {"advanced": False, "reason": "incomplete", "attempts": len(attempts), "items": len(items)}
    correct = sum(1 for a in attempts if a.get("correct"))
    return consider_advance(user_id, tag, correct=correct, total=len(attempts), path=path)
