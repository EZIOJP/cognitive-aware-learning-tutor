"""Tag importance store, bars, density, progress, Low Mastery."""

from __future__ import annotations

import json
import os
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterator

from backend.paths import ROOT
from backend.quiz.atomic_io import atomic_write_text

STORE_PATH = ROOT / "data" / "quiz" / "tag_importance.json"
DEFAULT_IMPORTANCE = 3
BAR = {1: 2, 2: 3, 3: 4, 4: 5, 5: 6}
INTERVAL_FACTOR = {1: 1.25, 2: 1.0, 3: 0.85, 4: 0.70, 5: 0.55}


def clamp_importance(n: int) -> int:
    return max(1, min(5, int(n)))


def bar_for(importance: int) -> int:
    return BAR[clamp_importance(importance)]


def interval_factor_for(importance: int) -> float:
    return INTERVAL_FACTOR[clamp_importance(importance)]


@contextmanager
def _file_lock(lock_path: Path) -> Iterator[None]:
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    fh = open(lock_path, "a+", encoding="utf-8")
    try:
        if os.name == "nt":
            import msvcrt

            fh.seek(0)
            msvcrt.locking(fh.fileno(), msvcrt.LK_LOCK, 1)
        else:
            import fcntl

            fcntl.flock(fh.fileno(), fcntl.LOCK_EX)
        yield
    finally:
        if os.name == "nt":
            import msvcrt

            fh.seek(0)
            try:
                msvcrt.locking(fh.fileno(), msvcrt.LK_UNLCK, 1)
            except OSError:
                pass
        else:
            import fcntl

            fcntl.flock(fh.fileno(), fcntl.LOCK_UN)
        fh.close()


def empty_store() -> dict[str, Any]:
    return {"schema_version": 1, "default_importance": DEFAULT_IMPORTANCE, "tags": {}}


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
    data.setdefault("default_importance", DEFAULT_IMPORTANCE)
    data.setdefault("tags", {})
    return data


def importance_for(tag_id: str, store: dict[str, Any] | None = None) -> int:
    st = store or load_store()
    row = (st.get("tags") or {}).get(tag_id)
    if not row:
        return int(st.get("default_importance") or DEFAULT_IMPORTANCE)
    return clamp_importance(int(row.get("importance") or DEFAULT_IMPORTANCE))


def effective_importance(tag_ids: list[str], store: dict[str, Any] | None = None) -> int:
    st = store or load_store()
    if not tag_ids:
        return int(st.get("default_importance") or DEFAULT_IMPORTANCE)
    return max(importance_for(t, st) for t in tag_ids)


def apply_density(interval_days: int, importance: int) -> int:
    scaled = interval_days * interval_factor_for(importance)
    return max(1, int(round(scaled)))


def put_importance(
    tag_id: str,
    importance: int,
    *,
    note: str | None = None,
    expected_updated_at: str | None = None,
    source: str = "user",
    path: Path | None = None,
) -> dict[str, Any]:
    p = path or STORE_PATH
    lock = p.with_suffix(p.suffix + ".lock")
    tid = (tag_id or "").strip()
    if not tid:
        raise ValueError("tag required")
    imp = clamp_importance(importance)
    with _file_lock(lock):
        store = load_store(p)
        tags = store.setdefault("tags", {})
        existing = tags.get(tid)
        now = datetime.now(UTC).isoformat().replace("+00:00", "Z")
        expected = expected_updated_at if expected_updated_at not in ("",) else None
        if existing is None:
            if expected is not None:
                raise ValueError("mtime_conflict")
        else:
            stored = str(existing.get("updated_at") or "")
            if expected is None or expected != stored:
                raise ValueError("mtime_conflict")
        tags[tid] = {
            "importance": imp,
            "source": source,
            "updated_at": now,
            "note": note if note is not None else (existing or {}).get("note"),
        }
        if tags[tid].get("note") is None:
            tags[tid].pop("note", None)
        p.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_text(p, json.dumps(store, indent=2, ensure_ascii=False) + "\n")
        return tags[tid]


def apply_suggest_writes(
    suggestions: list[dict[str, Any]],
    *,
    known_tags: set[str],
    overwrite_claude: bool,
    path: Path | None = None,
) -> dict[str, Any]:
    p = path or STORE_PATH
    lock = p.with_suffix(p.suffix + ".lock")
    updated: list[dict[str, Any]] = []
    skipped_user: list[dict[str, Any]] = []
    skipped_claude: list[dict[str, Any]] = []
    dropped_invalid: list[dict[str, Any]] = []

    valid_rows: list[tuple[str, int, str | None]] = []
    for raw in suggestions:
        tid = str(raw.get("tag_id") or "").strip()
        try:
            imp = int(raw.get("importance"))
        except (TypeError, ValueError):
            dropped_invalid.append({"tag_id": tid or "?", "reason": "importance_out_of_range", "got": raw.get("importance")})
            continue
        if tid not in known_tags:
            dropped_invalid.append({"tag_id": tid or "?", "reason": "unknown_tag"})
            continue
        if imp < 1 or imp > 5:
            dropped_invalid.append({"tag_id": tid, "reason": "importance_out_of_range", "got": imp})
            continue
        note = raw.get("note")
        valid_rows.append((tid, imp, str(note) if note else None))

    with _file_lock(lock):
        store = load_store(p)
        tags = store.setdefault("tags", {})
        now = datetime.now(UTC).isoformat().replace("+00:00", "Z")
        for tid, imp, note in valid_rows:
            existing = tags.get(tid)
            src = str((existing or {}).get("source") or "default")
            if src == "user":
                skipped_user.append({"tag_id": tid, "reason": "user_locked"})
                continue
            if src == "claude" and not overwrite_claude:
                skipped_claude.append({"tag_id": tid, "reason": "claude_locked"})
                continue
            row = {
                "importance": imp,
                "source": "claude",
                "updated_at": now,
            }
            if note:
                row["note"] = note
            tags[tid] = row
            updated.append({"tag_id": tid, "importance": imp})
        p.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_text(p, json.dumps(store, indent=2, ensure_ascii=False) + "\n")

    return {
        "updated": updated,
        "skipped_user": skipped_user,
        "skipped_claude": skipped_claude,
        "dropped_invalid": dropped_invalid,
    }


def card_tag_ids(payload: dict[str, Any], topic: str | None = None) -> list[str]:
    out: list[str] = []
    for t in list(payload.get("tags") or []) + list(payload.get("note_topic_ids") or []):
        s = str(t).strip()
        if s and s not in out:
            out.append(s)
    if topic and str(topic).strip() and str(topic).strip() not in out:
        out.append(str(topic).strip())
    return out


def days_overdue(due_iso: str | None, *, now: datetime | None = None, owes: int = 0) -> int:
    now = now or datetime.now(UTC)
    days = 0
    if due_iso:
        due = datetime.fromisoformat(str(due_iso).replace("Z", "+00:00")).astimezone(UTC)
        days = max(0, int((now - due).total_seconds() // 86400))
    if owes > 0:
        days = max(days, 1)
    return days


def queue_score(
    *,
    importance: int,
    due_iso: str | None,
    owes: int,
    item_key: str,
) -> tuple[float, int, str]:
    d = days_overdue(due_iso, owes=owes)
    score = clamp_importance(importance) * (1 + d)
    return (-score, -int(owes or 0), item_key)


def session_bar_for(session_tag: str | None, tag_ids: list[str], store: dict[str, Any] | None = None) -> int:
    st = store or load_store()
    if session_tag:
        return bar_for(importance_for(session_tag, st))
    return bar_for(effective_importance(tag_ids, st))


def recycle_insert_index(current_index: int, n_items: int, rng: Any | None = None) -> int:
    """Insert position for a recycle item (after the answered card)."""
    import random as _random

    rng = rng or _random
    remaining = n_items - current_index - 1
    if remaining < 3:
        return n_items
    skip = rng.randint(3, min(7, remaining))
    return current_index + 1 + skip


def apply_learning_grade(
    state: Any,
    *,
    correct: bool,
    elapsed_ms: int = 0,
    payload: dict[str, Any] | None = None,
    topic: str | None = None,
    session_tag: str | None = None,
    store: dict[str, Any] | None = None,
) -> Any:
    """Grade one ReviewCard: recycle if owing, else full FSRS + density + Learning entry."""
    from datetime import timedelta

    from backend.quiz import srs as srs_mod

    payload = payload or {}
    st = store or load_store()
    tags = card_tag_ids(payload, topic)
    bar = session_bar_for(session_tag, tags, st)
    if int(getattr(state, "owes_corrects", 0) or 0) > 0:
        return srs_mod.apply_recycle_answer(state, correct=correct)

    state = srs_mod.schedule_after_answer(state, correct=correct, elapsed_ms=elapsed_ms)
    imp = effective_importance(tags, st)
    state.interval_days = apply_density(int(state.interval_days or 1), imp)
    now = datetime.now(UTC)
    state.due_date = now + timedelta(days=state.interval_days)
    if not correct and int(state.mastery) < bar:
        state.owes_corrects = 2
    return state


def card_linked_to_tag(payload: dict[str, Any], topic: str | None, tag_id: str) -> bool:
    want = (tag_id or "").strip()
    if not want:
        return False
    want_l = want.lower()
    for t in card_tag_ids(payload, topic):
        if str(t).strip().lower() == want_l:
            return True
    if want_l.startswith("vocab.group."):
        try:
            gn = int(want_l.rsplit(".", 1)[-1])
        except ValueError:
            gn = None
        if gn is not None and int(payload.get("group_number") or 0) == gn:
            return True
    return False


def progress_for_tag(
    cards: list[Any],
    tag_id: str,
    store: dict[str, Any] | None = None,
) -> dict[str, Any]:
    import json as _json

    from backend.quiz import srs as srs_mod

    st = store or load_store()
    bar = bar_for(importance_for(tag_id, st))
    total = 0
    cleared = 0
    owes_count = 0
    for card in cards:
        payload = _json.loads(getattr(card, "payload_json", None) or "{}")
        topic = getattr(card, "topic", None)
        if not card_linked_to_tag(payload, topic, tag_id):
            continue
        total += 1
        state = srs_mod.srs_from_metadata(_json.loads(getattr(card, "srs_json", None) or "{}"))
        if int(state.owes_corrects or 0) > 0:
            owes_count += 1
        if int(state.mastery) >= bar:
            cleared += 1
    mastered = total > 0 and cleared == total
    return {
        "cleared": cleared,
        "total": total,
        "mastered": mastered,
        "bar": bar,
        "weak_count": max(0, total - cleared),
        "owes_count": owes_count,
    }


def list_low_mastery(
    cards: list[Any],
    tag_ids: list[str],
    store: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    st = store or load_store()
    rows: list[dict[str, Any]] = []
    for tid in tag_ids:
        prog = progress_for_tag(cards, tid, st)
        if prog["total"] == 0 or prog["mastered"]:
            continue
        rows.append(
            {
                "tag_id": tid,
                "importance": importance_for(tid, st),
                "bar": prog["bar"],
                "cleared": prog["cleared"],
                "total": prog["total"],
                "weak_count": prog["weak_count"],
                "owes_count": prog["owes_count"],
            }
        )
    rows.sort(key=lambda r: (-int(r["importance"]), -int(r["weak_count"]), r["tag_id"]))
    return rows


def weak_cards_for_session(
    cards: list[Any],
    *,
    tag: str | None,
    store: dict[str, Any] | None = None,
) -> list[Any]:
    import json as _json

    from backend.quiz import srs as srs_mod

    st = store or load_store()
    out: list[Any] = []
    for card in cards:
        payload = _json.loads(getattr(card, "payload_json", None) or "{}")
        topic = getattr(card, "topic", None)
        tags = card_tag_ids(payload, topic)
        if tag and not card_linked_to_tag(payload, topic, tag):
            continue
        if not tag and not tags:
            continue
        state = srs_mod.srs_from_metadata(_json.loads(getattr(card, "srs_json", None) or "{}"))
        if tag:
            bar = bar_for(importance_for(tag, st))
            if int(state.mastery) >= bar and int(state.owes_corrects or 0) == 0:
                continue
        else:
            weak = False
            for t in tags:
                bar = bar_for(importance_for(t, st))
                if int(state.mastery) < bar or int(state.owes_corrects or 0) > 0:
                    weak = True
                    break
            if not weak:
                continue
        out.append(card)
    return out


def sort_cards_for_queue(
    cards: list[Any],
    *,
    session_tag: str | None,
    store: dict[str, Any] | None = None,
) -> list[Any]:
    import json as _json

    from backend.quiz import srs as srs_mod

    st = store or load_store()

    def _key(card: Any) -> tuple[float, int, str]:
        payload = _json.loads(getattr(card, "payload_json", None) or "{}")
        topic = getattr(card, "topic", None)
        tags = card_tag_ids(payload, topic)
        if session_tag:
            i = importance_for(session_tag, st)
        else:
            i = effective_importance(tags, st)
        state = srs_mod.srs_from_metadata(_json.loads(getattr(card, "srs_json", None) or "{}"))
        due = None
        if state.due_date is not None:
            due = state.due_date.astimezone(UTC).isoformat().replace("+00:00", "Z")
        return queue_score(
            importance=i,
            due_iso=due,
            owes=int(state.owes_corrects or 0),
            item_key=str(getattr(card, "item_key", "")),
        )

    return sorted(cards, key=_key)


def ephemeral_math_recycle(item: dict[str, Any]) -> dict[str, Any]:
    """New numbers for a math recycle; never writes the question bank."""
    from backend.quiz import math_generators as mg

    out = dict(item)
    recipe = None
    gen_id = item.get("gen_id")
    if gen_id is not None:
        try:
            gid = int(gen_id)
        except (TypeError, ValueError):
            gid = None
        if gid is not None:
            for r in mg.list_recipes():
                if r.gen_id == gid:
                    recipe = r
                    break
    if recipe is None:
        ntid = ""
        nids = item.get("note_topic_ids") or []
        if nids:
            ntid = str(nids[0])
        ntid = ntid or str(item.get("topic_id") or item.get("topic") or "")
        recs = mg.recipes_for_note_topic(ntid) if ntid else []
        recipe = recs[0] if recs else None
    if recipe is None:
        return out
    pair = mg.generate_one(recipe)
    if not pair:
        return out
    prompt, answer = pair
    out["prompt"] = prompt
    out["expected_answer"] = answer
    out["_ephemeral"] = True
    return out


class SuggestLlmError(RuntimeError):
    pass


def run_suggest(
    *,
    tags: list[str] | None,
    overwrite_claude: bool,
    known_tags: set[str],
    llm_text: str | None,
    path: Path | None = None,
) -> dict[str, Any]:
    if llm_text is None:
        raise SuggestLlmError("llm_failed")
    raw = llm_text.strip()
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        start = raw.find("[")
        end = raw.rfind("]")
        if start >= 0 and end > start:
            data = json.loads(raw[start : end + 1])
        else:
            raise SuggestLlmError("llm_failed") from None
    rows: list[dict[str, Any]]
    if isinstance(data, list):
        rows = [x for x in data if isinstance(x, dict)]
    elif isinstance(data, dict):
        inner = data.get("suggestions") or data.get("tags") or []
        rows = [x for x in inner if isinstance(x, dict)]
    else:
        rows = []
    want = set(tags) if tags else known_tags
    filtered: list[dict[str, Any]] = []
    for row in rows:
        tid = str(row.get("tag_id") or "").strip()
        if tags is not None and tid not in want and tid not in known_tags:
            filtered.append(row)
            continue
        filtered.append(row)
    return apply_suggest_writes(
        filtered,
        known_tags=known_tags,
        overwrite_claude=overwrite_claude,
        path=path,
    )
