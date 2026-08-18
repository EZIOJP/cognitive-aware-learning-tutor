"""Bible day progress, bookmarks, reader position (JSON under data/bible/)."""

from __future__ import annotations

import json
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from backend.bible.paths import bible_dir
from backend.planner.service import local_tz

BIBLE_CHUNK_S = 30 * 60  # legacy bank chunks (secondary; chapter goal is primary)
HEARTBEAT_MAX_GAP_S = 45
HEARTBEAT_CREDIT_S = 25  # per successful focused heartbeat
# Day goal completes ONLY via tick_chapter / toggle_chapter_manual — never from dwell or PDF page.
CHAPTER_GOAL_TARGET = 1  # daily Bible goal
# Controlled skip: max day-passes per Mon–Sun week (must type PASS to confirm)
DAY_PASSES_PER_WEEK = 2


def _day_key() -> str:
    # Always real wall clock — never demo_clock (demo must not reset Bible progress).
    return datetime.now(local_tz()).date().isoformat()


def _day_path(user_id: int) -> Path:
    return bible_dir() / f"day_{user_id}_{_day_key()}.json"


def _bookmarks_path(user_id: int) -> Path:
    return bible_dir() / f"bookmarks_{user_id}.json"


def _reader_path(user_id: int) -> Path:
    return bible_dir() / f"reader_{user_id}.json"


def _read_json(path: Path, default: Any) -> Any:
    if not path.is_file():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


def _write_json(path: Path, data: Any) -> None:
    """Atomic replace — avoids empty/corrupt reads during concurrent tick + heartbeat."""
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(data, indent=2)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(payload, encoding="utf-8")
    os.replace(tmp, path)


def _empty_day() -> dict[str, Any]:
    return {
        "day": _day_key(),
        "bible_seconds": 0,
        "game_consumed_seconds": 0,
        "last_heartbeat_at": 0.0,
        "day_pass": False,
        "reward_day": False,
        "chapters_completed": [],
        "chapter_dwell": {},
        "assigned_book": None,
        "assigned_chapter": None,
    }


def load_day(user_id: int) -> dict[str, Any]:
    raw = _read_json(_day_path(user_id), _empty_day())
    if raw.get("day") != _day_key():
        raw = _empty_day()
    if not isinstance(raw.get("chapters_completed"), list):
        raw["chapters_completed"] = []
    if not isinstance(raw.get("chapter_dwell"), dict):
        raw["chapter_dwell"] = {}
    return raw


def _plan_index(key: str | None) -> int:
    if not key:
        return -1
    try:
        from backend.bible import structured as bible_text

        plan = bible_text.sequential_plan("web")
        for i, row in enumerate(plan):
            if row["key"] == key:
                return i
    except Exception:
        return -1
    return -1


def save_day(
    user_id: int,
    data: dict[str, Any],
    *,
    replace_completed: bool = False,
) -> None:
    """Persist day JSON. Merges concurrent ticks so heartbeats cannot wipe completions."""
    try:
        from backend.behavior.demo_clock import is_demo

        if is_demo():
            # Read-only demo: never persist bible day JSON.
            return
    except Exception:
        pass
    path = _day_path(user_id)
    data = dict(data)
    data["day"] = _day_key()
    on_disk = _read_json(path, None)
    if isinstance(on_disk, dict) and on_disk.get("day") == _day_key():
        if replace_completed:
            pass  # trust caller (explicit untick / full replace)
        else:
            merged = set(on_disk.get("chapters_completed") or []) | set(
                data.get("chapters_completed") or []
            )
            data["chapters_completed"] = sorted(merged)
        # Keep the furthest assignment if two writers race
        disk_key = on_disk.get("assigned_key")
        mem_key = data.get("assigned_key")
        if _plan_index(str(disk_key) if disk_key else None) > _plan_index(
            str(mem_key) if mem_key else None
        ):
            data["assigned_book"] = on_disk.get("assigned_book")
            data["assigned_chapter"] = on_disk.get("assigned_chapter")
            data["assigned_key"] = disk_key
        disk_dwell = on_disk.get("chapter_dwell") or {}
        mem_dwell = data.get("chapter_dwell") or {}
        if isinstance(disk_dwell, dict) and isinstance(mem_dwell, dict):
            out_dwell: dict[str, Any] = dict(disk_dwell)
            for k, v in mem_dwell.items():
                out_dwell[k] = max(int(out_dwell.get(k) or 0), int(v or 0))
            data["chapter_dwell"] = out_dwell
        data["bible_seconds"] = max(
            int(on_disk.get("bible_seconds") or 0), int(data.get("bible_seconds") or 0)
        )
        data["game_consumed_seconds"] = max(
            int(on_disk.get("game_consumed_seconds") or 0),
            int(data.get("game_consumed_seconds") or 0),
        )
        data["last_heartbeat_at"] = max(
            float(on_disk.get("last_heartbeat_at") or 0),
            float(data.get("last_heartbeat_at") or 0),
        )
        if on_disk.get("day_pass"):
            data["day_pass"] = True
        if on_disk.get("reward_day"):
            data["reward_day"] = True
    _write_json(path, data)


def bible_seconds(user_id: int) -> int:
    return max(0, int(load_day(user_id).get("bible_seconds") or 0))


def game_bank_earned_seconds(user_id: int) -> int:
    """30 min Bible → 30 min bank, stacking by full chunks."""
    return (bible_seconds(user_id) // BIBLE_CHUNK_S) * BIBLE_CHUNK_S


def game_bank_remaining_seconds(user_id: int) -> int:
    day = load_day(user_id)
    earned = (max(0, int(day.get("bible_seconds") or 0)) // BIBLE_CHUNK_S) * BIBLE_CHUNK_S
    consumed = max(0, int(day.get("game_consumed_seconds") or 0))
    return max(0, earned - consumed)


def consume_game_seconds(user_id: int, seconds: float) -> int:
    """Drain bank while gaming. Returns remaining seconds after drain."""
    if seconds <= 0:
        return game_bank_remaining_seconds(user_id)
    day = load_day(user_id)
    day["game_consumed_seconds"] = max(0, int(day.get("game_consumed_seconds") or 0)) + int(
        max(0, seconds)
    )
    save_day(user_id, day)
    return game_bank_remaining_seconds(user_id)


def recover_lifetime_from_day_logs(user_id: int) -> list[str]:
    """Rebuild completed keys from day_*.json when reader progress was wiped."""
    from backend.bible import structured as bible_text

    found: set[str] = set()
    for p in sorted(bible_dir().glob(f"day_{user_id}_*.json")):
        raw = _read_json(p, {})
        if not isinstance(raw, dict):
            continue
        for c in raw.get("chapters_completed") or []:
            found.add(str(c))
        # assigned_key is today's reading, not a completed chapter. Treating it as
        # lifetime progress made resolve_today_chapter skip Genesis 1 on a fresh day.
    if not found:
        return []
    plan = bible_text.sequential_plan("web")
    max_i = -1
    for i, row in enumerate(plan):
        if row["key"] in found:
            max_i = i
    if max_i < 0:
        return sorted(found)
    return [plan[i]["key"] for i in range(max_i + 1)]


def _patch_reader(user_id: int, **fields: Any) -> dict[str, Any]:
    """Merge-safe reader update — never drops completed_chapters on heartbeat races."""
    path = _reader_path(user_id)
    reader = _read_json(path, {})
    if not isinstance(reader, dict):
        reader = {}
    on_disk = _read_json(path, {})
    if isinstance(on_disk, dict):
        # Prefer non-empty lifetime lists from disk if in-memory lost them
        for key in ("completed_chapters", "manual_chapters", "cleared_chapters"):
            disk_list = on_disk.get(key) if isinstance(on_disk.get(key), list) else []
            mem_list = reader.get(key) if isinstance(reader.get(key), list) else []
            if key in fields and isinstance(fields[key], list):
                if fields.get("_replace_lists"):
                    reader[key] = list(fields[key])
                else:
                    reader[key] = sorted(set(disk_list) | set(mem_list) | set(fields[key]))
            else:
                reader[key] = sorted(set(disk_list) | set(mem_list))
        disk_cursor = on_disk.get("plan_cursor")
        mem_cursor = reader.get("plan_cursor")
        if "plan_cursor" in fields:
            reader["plan_cursor"] = fields["plan_cursor"]
        elif disk_cursor is not None or mem_cursor is not None:
            try:
                reader["plan_cursor"] = max(int(disk_cursor or 0), int(mem_cursor or 0))
            except (TypeError, ValueError):
                reader["plan_cursor"] = disk_cursor if disk_cursor is not None else mem_cursor
    for k, v in fields.items():
        if k.startswith("_") or k in (
            "completed_chapters",
            "manual_chapters",
            "cleared_chapters",
            "plan_cursor",
        ):
            continue
        reader[k] = v
    if "plan_cursor" in fields:
        reader["plan_cursor"] = fields["plan_cursor"]
    reader["updated_at"] = datetime.now(local_tz()).isoformat()
    _write_json(path, reader)
    return reader


def credit_reading_seconds(user_id: int, seconds: float) -> dict[str, Any]:
    """Add focused reading time (desktop tracker / local PDF). Caps burst per call."""
    add = int(max(0, min(seconds, 5)))  # at most 5s per poll tick
    if add <= 0:
        return summary(user_id)
    day = load_day(user_id)
    day["bible_seconds"] = max(0, int(day.get("bible_seconds") or 0)) + add
    day["last_heartbeat_at"] = time.time()
    save_day(user_id, day)
    return summary(user_id)


def apply_heartbeat(user_id: int, *, page: int, focused: bool) -> dict[str, Any]:
    """Legacy PDF-page heartbeat (still credits optional minutes)."""
    day = load_day(user_id)
    now = time.time()
    last = float(day.get("last_heartbeat_at") or 0)
    if focused and last > 0 and (now - last) <= HEARTBEAT_MAX_GAP_S:
        day["bible_seconds"] = max(0, int(day.get("bible_seconds") or 0)) + HEARTBEAT_CREDIT_S
    day["last_heartbeat_at"] = now
    save_day(user_id, day)

    _patch_reader(user_id, last_page=max(1, int(page or 1)))

    return summary(user_id)


def apply_chapter_heartbeat(
    user_id: int, *, book: str, chapter: int, focused: bool, verse: int = 1
) -> dict[str, Any]:
    """Verse-reader heartbeat: optional reading minutes only — never auto-ticks the day goal."""
    book = (book or "").strip()
    chapter = max(1, int(chapter or 1))
    if not book:
        return summary(user_id)

    from backend.bible.structured import chapter_key

    assigned = resolve_today_chapter(user_id)
    key = chapter_key(book, chapter)
    # Only today's assigned chapter earns optional minutes / dwell stats
    if key != assigned["key"]:
        return summary(user_id)

    day = load_day(user_id)
    now = time.time()
    last = float(day.get("last_heartbeat_at") or 0)
    if focused and last > 0 and (now - last) <= HEARTBEAT_MAX_GAP_S:
        credited = HEARTBEAT_CREDIT_S
        day["bible_seconds"] = max(0, int(day.get("bible_seconds") or 0)) + credited
        dwell = day.get("chapter_dwell") or {}
        dwell[key] = max(0, int(dwell.get(key) or 0)) + credited
        day["chapter_dwell"] = dwell
    day["last_heartbeat_at"] = now
    save_day(user_id, day)

    _patch_reader(
        user_id,
        last_book=book,
        last_chapter=chapter,
        last_verse=max(1, int(verse or 1)),
    )

    return summary(user_id)


def chapters_completed_today(user_id: int) -> list[str]:
    day = load_day(user_id)
    raw = day.get("chapters_completed") or []
    if not isinstance(raw, list):
        return []
    return [str(x) for x in raw if str(x)]


def chapter_goal_met(user_id: int) -> bool:
    return len(chapters_completed_today(user_id)) >= CHAPTER_GOAL_TARGET


def _bootstrap_plan_cursor(completed: set[str], plan: list[dict[str, Any]]) -> int:
    """Next unread index = one past the furthest completed chapter in plan order."""
    max_i = -1
    for i, row in enumerate(plan):
        if row["key"] in completed:
            max_i = i
    nxt = max_i + 1
    if not plan:
        return 0
    return min(max(0, nxt), len(plan) - 1)


def resolve_today_chapter(user_id: int, *, version: str = "web") -> dict[str, Any]:
    """
    One assigned chapter per local calendar day.

    Stable for the day (persisted on day_*.json). Next day advances via plan_cursor
    after today's chapter is completed (or bootstrap from lifetime completed).
    """
    from backend.bible import structured as bible_text

    day = load_day(user_id)
    plan = bible_text.sequential_plan(version)
    if not plan:
        return {
            "book": "Genesis",
            "chapter": 1,
            "key": "Genesis|1",
            "label": "Genesis 1",
            "done": False,
            "mode": "today_only",
        }

    lifetime = set(get_completed_chapters(user_id))
    desired_i = _bootstrap_plan_cursor(lifetime, plan)
    desired = plan[desired_i]
    today_done_keys = set(chapters_completed_today(user_id))

    ab = (day.get("assigned_book") or "").strip()
    ac = day.get("assigned_chapter")
    if ab and ac is not None:
        chapter = max(1, int(ac))
        key = bible_text.chapter_key(ab, chapter)
        # Wipe / race left a completed-history chapter as "today" — jump to next unread.
        if key in lifetime and key not in today_done_keys and desired["key"] != key:
            ab = str(desired["book"])
            chapter = int(desired["chapter"])
            key = str(desired["key"])
            day["assigned_book"] = ab
            day["assigned_chapter"] = chapter
            day["assigned_key"] = key
            save_day(user_id, day)
            _patch_reader(
                user_id,
                plan_cursor=desired_i,
                last_book=ab,
                last_chapter=chapter,
            )
    else:
        reader = _read_json(_reader_path(user_id), {})
        if "plan_cursor" in reader:
            cursor = max(0, min(int(reader.get("plan_cursor") or 0), len(plan) - 1))
            # Don't stay behind recovered lifetime
            cursor = max(cursor, desired_i)
        else:
            cursor = desired_i
        row = plan[cursor]
        ab = str(row["book"])
        chapter = int(row["chapter"])
        key = str(row["key"])
        day["assigned_book"] = ab
        day["assigned_chapter"] = chapter
        day["assigned_key"] = key
        save_day(user_id, day)
        _patch_reader(
            user_id,
            plan_cursor=cursor,
            last_book=ab,
            last_chapter=chapter,
        )

    today_done = key in chapters_completed_today(user_id)
    return {
        "book": ab,
        "chapter": chapter,
        "key": key,
        "label": f"{ab} {chapter}",
        "done": today_done or chapter_goal_met(user_id),
        "mode": "today_only",
    }


def _advance_plan_cursor(user_id: int, *, completed_key: str, advancing: bool) -> None:
    from backend.bible import structured as bible_text

    plan = bible_text.sequential_plan("web")
    if not plan:
        return
    try:
        idx = next(i for i, row in enumerate(plan) if row["key"] == completed_key)
    except StopIteration:
        return
    cursor = min(idx + 1, len(plan) - 1) if advancing else idx
    _patch_reader(user_id, plan_cursor=cursor)


def tick_chapter(
    user_id: int, *, book: str, chapter: int, done: bool = True
) -> dict[str, Any]:
    """Manual tick: mark today's assigned chapter complete (or untick)."""
    from backend.bible.structured import chapter_key

    book = (book or "").strip()
    chapter = max(1, int(chapter or 1))
    if not book:
        raise ValueError("book required")
    assigned = resolve_today_chapter(user_id)
    key = chapter_key(book, chapter)
    if key != assigned["key"]:
        raise ValueError(
            f"Only today's chapter ({assigned['label']}) can be marked done"
        )
    day = load_day(user_id)
    completed = set(chapters_completed_today(user_id))
    reader = _read_json(_reader_path(user_id), {})
    lifetime = set(get_completed_chapters(user_id))
    manual = set(get_manual_chapters(user_id))
    cleared = set(get_cleared_chapters(user_id))
    newly_done = False

    if done:
        newly_done = key not in completed
        completed.add(key)
        lifetime.add(key)
        manual.add(key)
        cleared.discard(key)
        _advance_plan_cursor(user_id, completed_key=key, advancing=True)
    else:
        completed.discard(key)
        lifetime.discard(key)
        manual.discard(key)
        cleared.add(key)
        _advance_plan_cursor(user_id, completed_key=key, advancing=False)

    day["chapters_completed"] = sorted(completed)
    # Keep assignment stable for the calendar day
    day["assigned_book"] = assigned["book"]
    day["assigned_chapter"] = assigned["chapter"]
    day["assigned_key"] = key
    save_day(user_id, day, replace_completed=not done)

    _patch_reader(
        user_id,
        completed_chapters=sorted(lifetime),
        manual_chapters=sorted(manual),
        cleared_chapters=sorted(cleared),
        last_book=book,
        last_chapter=chapter,
        _replace_lists=not done,
    )

    rewards = _maybe_morning_bible_reward(user_id)
    out = {
        "ok": True,
        "key": key,
        "done": key in completed,
        **summary(user_id),
    }
    if rewards is not None:
        out["morning_rewards"] = rewards
    if newly_done:
        # Praise only — do not silently allocate planner blocks after Bible.
        # User drafts via Productivity “Draft auto plan” / morning-plan/auto-draft.
        try:
            from backend.behavior.voice_agent.dialogues import speak

            speak("bible_done_praise", force=True)
        except Exception:
            pass
    return out


def summary(user_id: int) -> dict[str, Any]:
    day = load_day(user_id)
    bible_s = max(0, int(day.get("bible_seconds") or 0))
    earned = (bible_s // BIBLE_CHUNK_S) * BIBLE_CHUNK_S
    consumed = max(0, int(day.get("game_consumed_seconds") or 0))
    remaining = max(0, earned - consumed)
    reader = _read_json(_reader_path(user_id), {"last_page": 1})
    today_chapters = chapters_completed_today(user_id)
    today_ch = resolve_today_chapter(user_id)
    return {
        "day": _day_key(),
        "bible_minutes": round(bible_s / 60, 1),
        "bible_seconds": bible_s,
        "bible_chunk_minutes": 30,
        "next_bank_in_minutes": max(0, round((BIBLE_CHUNK_S - (bible_s % BIBLE_CHUNK_S)) / 60, 1))
        if bible_s % BIBLE_CHUNK_S
        else (0 if bible_s > 0 else 30),
        "game_bank_remaining_minutes": round(remaining / 60, 1),
        "game_bank_remaining_seconds": remaining,
        "game_bank_earned_minutes": round(earned / 60, 1),
        "game_bank_earned_seconds": earned,
        "game_bank_consumed_minutes": round(consumed / 60, 1),
        "game_bank_consumed_seconds": consumed,
        "day_pass": bool(day.get("day_pass")),
        "day_pass_status": day_pass_status(user_id) if user_id else None,
        "reward_day": bool(day.get("reward_day")),
        "last_page": max(1, int(reader.get("last_page") or 1)),
        "last_book": str(today_ch.get("book") or reader.get("last_book") or "Genesis"),
        "last_chapter": max(1, int(today_ch.get("chapter") or reader.get("last_chapter") or 1)),
        "last_verse": max(1, int(reader.get("last_verse") or 1)),
        "today_chapter": today_ch,
        "chapters_completed_today": today_chapters,
        "chapter_goal": {
            "done": len(today_chapters),
            "target": CHAPTER_GOAL_TARGET,
            "met": len(today_chapters) >= CHAPTER_GOAL_TARGET,
        },
        "completed_chapters": get_completed_chapters(user_id),
    }


def grant_day_pass(user_id: int) -> dict[str, Any]:
    """Unlock games until local midnight (manual day pass). Does not enforce weekly quota."""
    day = load_day(user_id)
    day["day_pass"] = True
    day["game_consumed_seconds"] = 0
    save_day(user_id, day)
    return summary(user_id)


def _passes_path(user_id: int) -> Path:
    return bible_dir() / f"day_passes_{user_id}.json"


def _week_monday_key() -> str:
    today = datetime.now(local_tz()).date()
    monday = today.fromordinal(today.toordinal() - today.weekday())  # Mon=0
    return monday.isoformat()


def day_pass_status(user_id: int) -> dict[str, Any]:
    """Weekly quota for controlled skips (no Bible required that day)."""
    week = _week_monday_key()
    today = _day_key()
    raw = _read_json(_passes_path(user_id), {"week": week, "dates": []})
    if raw.get("week") != week:
        raw = {"week": week, "dates": []}
    dates = [str(d) for d in (raw.get("dates") or []) if str(d)]
    used = len(dates)
    limit = DAY_PASSES_PER_WEEK
    already = today in dates or bool(load_day(user_id).get("day_pass"))
    return {
        "week_start": week,
        "limit": limit,
        "used": used,
        "remaining": max(0, limit - used),
        "already_active_today": already,
        "confirm_phrase": "PASS",
    }


def request_day_pass(user_id: int, *, confirm: str) -> dict[str, Any]:
    """Spend one weekly pass. Requires confirm == PASS."""
    if (confirm or "").strip().upper() != "PASS":
        raise ValueError("Type PASS to confirm a day pass")
    status = day_pass_status(user_id)
    week = status["week_start"]
    today = _day_key()
    raw = _read_json(_passes_path(user_id), {"week": week, "dates": []})
    if raw.get("week") != week:
        raw = {"week": week, "dates": []}
    dates = [str(d) for d in (raw.get("dates") or []) if str(d)]

    if status["already_active_today"]:
        # Count agent/manual grants toward the weekly quota if not recorded yet
        if today not in dates:
            if len(dates) >= DAY_PASSES_PER_WEEK:
                pass  # already over; still leave day unlocked
            else:
                dates.append(today)
                raw["week"] = week
                raw["dates"] = dates
                _write_json(_passes_path(user_id), raw)
        return {
            **summary(user_id),
            "day_pass_status": day_pass_status(user_id),
            "ok": True,
            "message": "Already unlocked today",
        }
    if status["remaining"] <= 0:
        raise ValueError(f"No day passes left this week ({status['used']}/{status['limit']})")
    if today not in dates:
        dates.append(today)
    raw["week"] = week
    raw["dates"] = dates
    _write_json(_passes_path(user_id), raw)
    out = grant_day_pass(user_id)
    return {
        **out,
        "day_pass_status": day_pass_status(user_id),
        "ok": True,
        "message": "Day pass granted — games unlocked until midnight",
    }


def get_last_page(user_id: int) -> int:
    """1-based last Bible page (defaults to 1)."""
    if not user_id:
        return 1
    reader = _read_json(_reader_path(user_id), {"last_page": 1})
    return max(1, int(reader.get("last_page") or 1))


def save_last_page(user_id: int, page: int) -> None:
    """Persist 1-based page so the embedded reader reopens here next time."""
    if not user_id:
        return
    _patch_reader(user_id, last_page=max(1, int(page)))


def get_completed_chapters(user_id: int) -> list[str]:
    """List of 'Book|N' keys marked complete (visual checkpoints, no bank reward)."""
    if not user_id:
        return []
    from backend.bible import structured as bible_text

    reader = _read_json(_reader_path(user_id), {})
    raw = reader.get("completed_chapters") or []
    if not isinstance(raw, list):
        raw = []
    keys = {str(x) for x in raw if str(x)}
    # Heal wipe: empty lifetime can be rebuilt from day logs. One completed chapter
    # is valid progress — do not treat it as a wipe.
    if not keys:
        recovered = recover_lifetime_from_day_logs(user_id)
        if recovered:
            keys |= set(recovered)
            plan = bible_text.sequential_plan("web")
            _patch_reader(
                user_id,
                completed_chapters=sorted(keys),
                plan_cursor=_bootstrap_plan_cursor(keys, plan),
            )
    return sorted(keys)


def get_manual_chapters(user_id: int) -> list[str]:
    if not user_id:
        return []
    reader = _read_json(_reader_path(user_id), {})
    raw = reader.get("manual_chapters") or []
    if not isinstance(raw, list):
        return []
    return [str(x) for x in raw]


def get_cleared_chapters(user_id: int) -> list[str]:
    """Chapters the user manually un-ticked (auto-detect won't force them back on)."""
    if not user_id:
        return []
    reader = _read_json(_reader_path(user_id), {})
    raw = reader.get("cleared_chapters") or []
    if not isinstance(raw, list):
        return []
    return [str(x) for x in raw]


def _sync_day_chapters(user_id: int, *, add: set[str] | None = None, remove: set[str] | None = None) -> None:
    """Keep day chapters_completed in sync with tracker/web ticks (morning gate)."""
    day = load_day(user_id)
    completed = set(chapters_completed_today(user_id))
    if add:
        completed |= {str(k) for k in add}
    if remove:
        completed -= {str(k) for k in remove}
    day["chapters_completed"] = sorted(completed)
    save_day(user_id, day)


def _maybe_morning_bible_reward(user_id: int) -> dict[str, Any] | None:
    try:
        from backend.planner import morning_rewards as rewards

        return rewards.maybe_grant_bible(user_id)
    except Exception:
        return None


def mark_chapters_complete(user_id: int, keys: set[str] | list[str]) -> list[str]:
    """
    Legacy PDF page-through visual checkpoints only.

    Does NOT mark the day goal, advance plan_cursor, or grant morning rewards —
    those require an explicit tick_chapter / toggle_chapter_manual.
    """
    if not user_id:
        return []
    reader = _read_json(_reader_path(user_id), {"last_page": 1})
    existing = set(get_completed_chapters(user_id))
    manual = set(get_manual_chapters(user_id))
    cleared = set(get_cleared_chapters(user_id))
    incoming = {str(k) for k in keys} - cleared
    existing |= incoming | manual
    reader["completed_chapters"] = sorted(existing)
    reader["manual_chapters"] = sorted(manual)
    reader["cleared_chapters"] = sorted(cleared)
    reader["updated_at"] = datetime.now(local_tz()).isoformat()
    _write_json(_reader_path(user_id), reader)
    return reader["completed_chapters"]


def toggle_chapter_manual(user_id: int, key: str) -> dict[str, Any]:
    """Tick/untick today's assigned chapter only (web + tracker share day goal)."""
    key = str(key)
    if not user_id or "|" not in key:
        return {"ok": False, "completed": False}
    assigned = resolve_today_chapter(user_id)
    if key != assigned["key"]:
        return {
            "ok": False,
            "completed": False,
            "error": f"Only today's chapter ({assigned['label']}) can be marked done",
            "today_chapter": assigned,
        }
    book, _, ch_s = key.partition("|")
    try:
        chapter = int(ch_s)
    except ValueError:
        return {"ok": False, "completed": False}
    out = tick_chapter(user_id, book=book, chapter=chapter, done=key not in chapters_completed_today(user_id))
    return {
        "ok": True,
        "completed": bool(out.get("done")),
        "key": key,
        "manual": bool(out.get("done")),
        "morning_rewards": out.get("morning_rewards"),
        "today_chapter": out.get("today_chapter"),
    }


def list_bookmarks(user_id: int) -> list[dict[str, Any]]:
    raw = _read_json(_bookmarks_path(user_id), [])
    if not isinstance(raw, list):
        return []
    out = []
    for i, b in enumerate(raw):
        if not isinstance(b, dict):
            continue
        out.append(
            {
                "id": int(b.get("id") or i + 1),
                "page": max(1, int(b.get("page") or 1)),
                "label": str(b.get("label") or f"Page {b.get('page') or 1}")[:120],
                "created_at": b.get("created_at"),
            }
        )
    return out


def add_bookmark(user_id: int, page: int, label: str = "") -> dict[str, Any]:
    items = list_bookmarks(user_id)
    nid = max([b["id"] for b in items], default=0) + 1
    row = {
        "id": nid,
        "page": max(1, int(page)),
        "label": (label or f"Page {page}").strip()[:120],
        "created_at": datetime.now(local_tz()).isoformat(),
    }
    items.append(row)
    _write_json(_bookmarks_path(user_id), items)
    return row


def delete_bookmark(user_id: int, bookmark_id: int) -> bool:
    items = list_bookmarks(user_id)
    nxt = [b for b in items if b["id"] != int(bookmark_id)]
    if len(nxt) == len(items):
        return False
    _write_json(_bookmarks_path(user_id), nxt)
    return True
