"""LLM-propose planner blocks from productivity export (+ optional routines)."""

from __future__ import annotations

import json
import logging
import re
from datetime import date, datetime, timedelta, timezone
from typing import Any

from backend.core.ollama_client import ollama_generate
from backend.planner.service import wall_clock_on_date

log = logging.getLogger(__name__)

_DAY_NAMES = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")

_SYSTEM = """You are a study planner for AI/ML and Scaler coursework.
Given productivity export (peak hours, patterns), user goals, and fixed daily routines,
propose a realistic calendar of deep-work blocks for the requested date range.

Rules:
- Respect fixed routines — do NOT schedule deep work overlapping those times.
- Prefer historically productive peak hours for study blocks.
- Never schedule entertainment/gaming as productive work.
- Prefer categories: Coding Practice, Study / Reading, AI / ML, Coursework (Browser).
- Blocks should be 45–120 minutes; include short breaks between heavy blocks.
- Only propose blocks inside the given start date and horizon (number of days).
- Return ONLY valid JSON matching the schema — no markdown fences.
"""

_SCHEMA_HINT = {
    "blocks": [
        {
            "title": "Scaler DSA deep work",
            "category": "Coding Practice",
            "start_at": "2026-07-14T10:00:00+05:30",
            "end_at": "2026-07-14T11:30:00+05:30",
        }
    ],
    "rationale": "short explanation",
}


def _extract_json(text: str) -> dict[str, Any]:
    text = (text or "").strip()
    if not text:
        raise ValueError("empty LLM response")
    fence = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if fence:
        text = fence.group(1).strip()
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start < 0 or end <= start:
            raise ValueError("no JSON object in LLM response") from None
        data = json.loads(text[start : end + 1])
    if not isinstance(data, dict):
        raise ValueError("LLM JSON must be an object")
    return data


def _monday_of(d: date) -> date:
    return d - timedelta(days=d.weekday())


def _parse_hm(t: str) -> tuple[int, int]:
    parts = (t or "09:00").split(":")
    return int(parts[0] or 0), int(parts[1] or 0) if len(parts) > 1 else 0


def _parse_daily_focus_hours(goals: str | None) -> float:
    text = goals or ""
    m = re.search(r"Daily effective-focus target:\s*([\d.]+)\s*h", text, re.I)
    if m:
        return max(0.5, min(12.0, float(m.group(1))))
    m2 = re.search(r"([\d.]+)\s*h(?:ours?)?\s*(?:per\s*day|/day|daily)", text, re.I)
    if m2:
        return max(0.5, min(12.0, float(m2.group(1))))
    return 3.0


def _is_unproductive_label(title: str, category: str = "") -> bool:
    """True if this should never be scheduled as study/deep work."""
    blob = f"{title} {category}".lower()
    bad = (
        "gam",  # game, games, gaming
        "entertain",
        "netflix",
        "youtube",
        "twitch",
        "steam",
        "music",
        "spotify",
        "social",
        "instagram",
        "facebook",
        "tiktok",
        "shop",
        "idle",
        "distract",
        "reddit",
        "meme",
    )
    return any(b in blob for b in bad)


def _goal_study_titles(goals: str | None, export: dict[str, Any] | None = None) -> list[tuple[str, str]]:
    """
    Study titles from goals only — never from tracker entertainment categories.
    Tracker top_categories often include Gaming; those must not become study blocks.
    """
    del export  # intentionally unused — do not mine tracker for titles
    text = (goals or "").strip()
    titles: list[tuple[str, str]] = []
    main = re.split(r"Daily effective-focus|Weekly target|Reward:|Extra goals", text, maxsplit=1)[
        0
    ].strip(" —.-•\n")
    low = main.lower()

    # Keyword-driven productive slices (Scaler / AI-ML profile)
    if any(k in low for k in ("scaler", "course", "lesson")):
        titles.append(("Scaler — daily lessons", "Coursework (Browser)"))
    if any(k in low for k in ("practice", "dsa", "coding", "code")):
        titles.append(("Scaler — practice / coding", "Coding Practice"))
    if any(k in low for k in ("ai", "ml", "machine learning", "deep learning")):
        titles.append(("AI/ML study block", "AI / ML"))
    if main and len(main) >= 8 and not titles:
        # Shorten long main goal to a clean study title
        short = re.split(r"\s*[—–]\s*", main)[0].strip()[:70]
        if short and not _is_unproductive_label(short):
            titles.append((short, "Coursework (Browser)"))

    defaults = [
        ("Scaler / coding practice", "Coding Practice"),
        ("AI/ML study block", "AI / ML"),
        ("Review + notes", "Study / Reading"),
    ]
    for d in defaults:
        if d[0] not in {t[0] for t in titles} and not _is_unproductive_label(d[0], d[1]):
            titles.append(d)
    return titles[:6]


def _parse_goal_slices(goals: str | None, export: dict[str, Any] | None = None) -> list[tuple[str, str]]:
    """Productive work slices from goals + extras (never gaming/entertainment)."""
    text = goals or ""
    slices: list[tuple[str, str]] = []

    # Start from keyword slices (Scaler lessons / practice / AI)
    for t in _goal_study_titles(goals, export):
        if not _is_unproductive_label(t[0], t[1]):
            slices.append(t)

    extras_m = re.search(r"Extra goals/todos:\s*(.+?)(?:\.\s*$|$)", text, re.I | re.S)
    if extras_m:
        for raw in re.split(r";", extras_m.group(1)):
            raw = raw.strip()
            if re.match(r"^\[done\]", raw, re.I):
                continue
            item = raw.strip(" .")
            if len(item) < 3 or _is_unproductive_label(item):
                continue
            slices.append((item[:90], "Study / Reading"))

    # Dedupe by title
    seen: set[str] = set()
    out: list[tuple[str, str]] = []
    for title, cat in slices:
        key = title.lower()
        if key in seen or _is_unproductive_label(title, cat):
            continue
        seen.add(key)
        out.append((title, cat))
    return out or [("Deep work — study", "Study / Reading")]


def _routine_interval_minutes(r: dict[str, Any]) -> tuple[int, int]:
    sh, sm = _parse_hm(str(r.get("start_time") or "09:00"))
    start_m = sh * 60 + sm
    if r.get("end_time"):
        eh, em = _parse_hm(str(r["end_time"]))
        end_m = eh * 60 + em
    else:
        end_m = start_m + max(1, int(r.get("duration_minutes") or 30))
    if end_m <= start_m:
        end_m = start_m + 30
    return start_m, end_m


def _overlaps_min(a0: int, a1: int, b0: int, b1: int) -> bool:
    return a0 < b1 and b0 < a1


def _find_free_slot(
    preferred_hour: int,
    duration_min: int,
    busy: list[tuple[int, int]],
    *,
    day_start_h: int = 7,
    day_end_h: int = 22,
) -> tuple[int, int] | None:
    """Find a free [start,end) in minutes-from-midnight near preferred_hour."""
    prefer = preferred_hour * 60
    candidates = [prefer]
    for delta in range(30, 10 * 60, 30):
        candidates.append(prefer + delta)
        candidates.append(prefer - delta)
    lo, hi = day_start_h * 60, day_end_h * 60
    for start_m in candidates:
        if start_m < lo or start_m + duration_min > hi:
            continue
        end_m = start_m + duration_min
        if any(_overlaps_min(start_m, end_m, b0, b1) for b0, b1 in busy):
            continue
        return start_m, end_m
    return None


def _peaks_for_weekday(export: dict[str, Any], weekday_key: str) -> list[int]:
    patterns = export.get("weekday_patterns") or {}
    wd = patterns.get(weekday_key) or {}
    peaks = wd.get("peak_hours") or []
    peaks = [int(h) for h in peaks if isinstance(h, (int, float))]
    if peaks:
        return peaks[:4]
    summary = export.get("summary") or {}
    global_peaks = summary.get("peak_hours") or [10, 14, 16]
    return [int(h) for h in global_peaks[:4]] or [10, 14, 16]


def _local_block_iso(day: date, start_m: int, end_m: int) -> tuple[str, str]:
    """Wall-clock local times (not UTC-labeled hours)."""
    sh, sm = divmod(max(0, start_m), 60)
    eh, em = divmod(max(start_m + 1, end_m), 60)
    start = wall_clock_on_date(day, f"{sh % 24:02d}:{sm:02d}")
    end = wall_clock_on_date(day, f"{eh % 24:02d}:{em:02d}")
    if end <= start:
        end = start + timedelta(minutes=30)
    return start.isoformat(), end.isoformat()


def _routine_blocks(
    routines: list[dict[str, Any]],
    range_start: date,
    horizon_days: int,
) -> list[dict[str, Any]]:
    """Materialize enabled routines across the horizon (rule-based, no LLM)."""
    blocks: list[dict[str, Any]] = []
    for offset in range(max(1, horizon_days)):
        day = range_start + timedelta(days=offset)
        key = _DAY_NAMES[day.weekday()]
        for r in routines:
            if not isinstance(r, dict):
                continue
            if r.get("enabled") is False:
                continue
            days = r.get("days") or list(_DAY_NAMES)
            if key not in days:
                continue
            title = str(r.get("title") or "Routine").strip()[:120]
            category = str(r.get("category") or "personal").strip()[:80]
            start_m, end_m = _routine_interval_minutes(r)
            start_at, end_at = _local_block_iso(day, start_m, end_m)
            blocks.append(
                {
                    "title": title,
                    "category": category,
                    "start_at": start_at,
                    "end_at": end_at,
                    "source": "routine",
                }
            )
    return blocks


def _free_gaps(
    busy: list[tuple[int, int]],
    *,
    day_start: int = 7 * 60,
    day_end: int = 22 * 60,
    min_gap: int = 45,
) -> list[tuple[int, int]]:
    """Return free [start,end) windows after merging busy intervals."""
    if day_end <= day_start:
        return []
    merged: list[tuple[int, int]] = []
    for a, b in sorted(busy):
        a, b = max(day_start, a), min(day_end, b)
        if b <= a:
            continue
        if merged and a <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], b))
        else:
            merged.append((a, b))
    gaps: list[tuple[int, int]] = []
    cursor = day_start
    for a, b in merged:
        if a - cursor >= min_gap:
            gaps.append((cursor, a))
        cursor = max(cursor, b)
    if day_end - cursor >= min_gap:
        gaps.append((cursor, day_end))
    return gaps


def _parse_weekly_focus_hours(goals: str | None) -> float | None:
    m = re.search(r"Weekly target:\s*([\d.]+)\s*h", goals or "", re.I)
    if m:
        return max(1.0, min(80.0, float(m.group(1))))
    return None


def _adherence_load_scale(export: dict[str, Any] | None) -> tuple[float, float | None]:
    """
    Soften next day's planned load from recent plan-vs-actual adherence.

    ≥80% → 1.0 · 60–80% → 0.9 · <60% → 0.8 · no data → 1.0
    Plan-locked: use capped adherence_pct / on-plan focus only — never raw productive.
    """
    by_day = (export or {}).get("by_day") or []
    ratios: list[float] = []
    for d in by_day:
        if not isinstance(d, dict):
            continue
        planned = float(d.get("planned_minutes") or 0)
        if planned < 30:
            continue
        if d.get("adherence_pct") is not None:
            ratios.append(min(100.0, float(d["adherence_pct"])))
            continue
        eff = d.get("on_plan_focus_minutes")
        if eff is None:
            eff = d.get("effective_focus_minutes")
        if eff is not None:
            ratios.append(min(100.0, 100.0 * float(eff) / planned))
    if not ratios:
        return 1.0, None
    avg = sum(ratios) / len(ratios)
    if avg >= 80:
        return 1.0, avg
    if avg >= 60:
        return 0.9, avg
    return 0.8, avg


def _day_focus_targets(
    goals: str | None,
    range_start: date,
    horizon_days: int,
    *,
    load_scale: float = 1.0,
) -> list[int]:
    """
    Per-day study minutes from step-1 daily focus target.

    Daily hours are the packing contract (user wants to *see* 4h when they set 4h).
    Weekends soft-trim slightly; weekly target is not used to shrink days.
    load_scale (0.8–1.0) softens target after weak adherence weeks.
    """
    daily_h = _parse_daily_focus_hours(goals)
    scale = max(0.75, min(1.0, float(load_scale or 1.0)))
    targets: list[int] = []
    for i in range(max(1, horizon_days)):
        day = range_start + timedelta(days=i)
        t = int(round(daily_h * 60 * scale))
        if horizon_days > 1 and day.weekday() >= 5:
            # Still aim near the daily goal on weekends (not half)
            t = max(90, int(round(t * 0.9)))
        targets.append(max(45, min(t, 10 * 60)))
    return targets


def _pack_gaps_with_goals(
    gaps: list[tuple[int, int]],
    target_min: int,
    slices: list[tuple[str, str]],
    peaks: list[int],
    *,
    slice_offset: int = 0,
    min_chunk: int = 30,
    preferred_chunk: int = 50,
) -> list[tuple[int, int, str, str]]:
    """
    Fill free gaps toward target_min with ~50m study chunks + short breaks.

    Stops at target_min (no overfill). Prefers a break after each chunk;
    requires a break before continuous study would exceed ~100m.
    """
    del peaks  # reserved for peak-hour bias later
    ordered = sorted(gaps, key=lambda g: g[0])
    out: list[tuple[int, int, str, str]] = []
    filled = 0
    si = slice_offset
    continuous_min = 0  # study minutes since last break
    chunks_since_break = 0
    pref = max(min_chunk, min(55, preferred_chunk))
    max_continuous = 100
    break_pref = 10

    for gap_start, gap_end in ordered:
        if filled >= target_min:
            break
        cursor = gap_start
        while cursor + min_chunk <= gap_end and filled < target_min:
            remaining_gap = gap_end - cursor
            remaining_target = target_min - filled
            need_break = chunks_since_break >= 1 or continuous_min >= pref
            force_break = continuous_min >= max_continuous - min_chunk
            if (need_break or force_break) and remaining_target > 0:
                room_for_study_after = remaining_gap - break_pref
                if room_for_study_after >= min_chunk or force_break:
                    br = min(break_pref, max(8, remaining_gap // 8))
                    if br >= 8 and cursor + br <= gap_end:
                        # Only insert break if we can still place study after, or must break
                        if cursor + br + min_chunk <= gap_end or force_break:
                            out.append((cursor, cursor + br, "Break", "break"))
                            cursor += br
                            continuous_min = 0
                            chunks_since_break = 0
                            if force_break and cursor + min_chunk > gap_end:
                                break
                            continue

            # Prefer ~50m (45–55); never schedule past remaining target
            want = min(pref, remaining_target, remaining_gap)
            if remaining_target >= 45 and remaining_gap >= 45 and remaining_target > pref:
                want = min(pref, remaining_gap)
            # Cap so continuous study stays under ~100m
            headroom = max_continuous - continuous_min
            if headroom < min_chunk and remaining_gap >= 8 + min_chunk:
                # insert mandatory break path on next loop
                continuous_min = max_continuous
                continue
            want = min(want, headroom if headroom >= min_chunk else want)
            duration = min(want, remaining_target, remaining_gap)
            if duration < min_chunk:
                # Take a short final slice if close to goal (≥20m leftover)
                if remaining_target >= 20 and remaining_gap >= 20 and filled + 20 <= target_min:
                    duration = min(remaining_target, remaining_gap)
                else:
                    break
            title, cat = slices[si % len(slices)]
            si += 1
            out.append((cursor, cursor + duration, title, cat))
            filled += duration
            continuous_min += duration
            chunks_since_break += 1
            cursor = cursor + duration  # breaks handle spacing; no silent +5 steal

    out.sort(key=lambda x: x[0])
    return out


def _busy_from_iso_blocks(
    blocks: list[dict[str, Any]],
    day: date,
) -> list[tuple[int, int]]:
    """Busy intervals from existing calendar / draft blocks on a local day."""
    from backend.planner.service import local_tz

    busy: list[tuple[int, int]] = []
    for b in blocks:
        if not isinstance(b, dict):
            continue
        try:
            s = datetime.fromisoformat(str(b.get("start_at") or "").replace("Z", "+00:00"))
            e = datetime.fromisoformat(str(b.get("end_at") or "").replace("Z", "+00:00"))
            if s.tzinfo is None:
                s = s.replace(tzinfo=timezone.utc)
            if e.tzinfo is None:
                e = e.replace(tzinfo=timezone.utc)
            sl = s.astimezone(local_tz())
            el = e.astimezone(local_tz())
            if sl.date() != day:
                continue
            sm = sl.hour * 60 + sl.minute
            em = el.hour * 60 + el.minute
            if el.date() > day:
                em = 24 * 60
            if em <= sm:
                em = sm + 30
            busy.append((sm, em))
        except Exception:
            continue
    return busy


def _cascade_resolve_blocks(blocks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Dedupe near-identical blocks and shift later ones so nothing overlaps (per local day)."""
    if len(blocks) <= 1:
        return blocks

    def _prio(src: str) -> int:
        return {"routine": 0, "existing": 1, "study": 2, "break": 3}.get(src or "study", 4)

    enriched: list[dict[str, Any]] = []
    for b in blocks:
        if not isinstance(b, dict):
            continue
        try:
            s = datetime.fromisoformat(str(b.get("start_at")).replace("Z", "+00:00"))
            e = datetime.fromisoformat(str(b.get("end_at")).replace("Z", "+00:00"))
            if s.tzinfo is None:
                s = s.replace(tzinfo=timezone.utc)
            if e.tzinfo is None:
                e = e.replace(tzinfo=timezone.utc)
            dur = max(10, int((e - s).total_seconds() // 60))
            local = s.astimezone()
            enriched.append(
                {
                    **b,
                    "_day": local.date(),
                    "_start_m": local.hour * 60 + local.minute,
                    "_dur": dur,
                }
            )
        except Exception:
            continue

    # Dedupe same title+source+start(~2m)
    deduped: list[dict[str, Any]] = []
    for b in enriched:
        skip = False
        for x in deduped:
            if (
                str(b.get("title") or "").strip().lower() == str(x.get("title") or "").strip().lower()
                and (b.get("source") or "study") == (x.get("source") or "study")
                and b["_day"] == x["_day"]
                and abs(int(b["_start_m"]) - int(x["_start_m"])) < 2
            ):
                skip = True
                break
        if not skip:
            deduped.append(b)

    by_day: dict[date, list[dict[str, Any]]] = {}
    for b in deduped:
        by_day.setdefault(b["_day"], []).append(b)

    out: list[dict[str, Any]] = []
    day_end = 23 * 60
    for day in sorted(by_day.keys()):
        row = sorted(
            by_day[day],
            key=lambda b: (int(b["_start_m"]), _prio(str(b.get("source") or "study"))),
        )
        cursor = -1
        for b in row:
            s = int(b["_start_m"])
            dur = int(b["_dur"])
            if s < cursor:
                s = cursor
            e = s + dur
            if e > day_end:
                if s >= day_end - 5:
                    continue
                e = day_end
                dur = e - s
                if dur < 10:
                    continue
            start_at, end_at = _local_block_iso(day, s, e)
            clean = {
                k: v
                for k, v in b.items()
                if not str(k).startswith("_")
            }
            clean["start_at"] = start_at
            clean["end_at"] = end_at
            out.append(clean)
            cursor = e
    return out


def _fallback_blocks(
    export: dict[str, Any],
    range_start: date,
    horizon_days: int,
    routines: list[dict[str, Any]] | None = None,
    goals: str | None = None,
    busy_blocks: list[dict[str, Any]] | None = None,
    *,
    load_scale: float = 1.0,
) -> list[dict[str, Any]]:
    """Gap-aware smart plan: protect routines + calendar → fill free gaps to daily goal hours."""
    routines = routines or []
    busy_blocks = busy_blocks or []
    blocks = _routine_blocks(routines, range_start, horizon_days)
    slices = _parse_goal_slices(goals, export)
    day_targets = _day_focus_targets(
        goals, range_start, horizon_days, load_scale=load_scale
    )
    slice_i = 0
    day_start, day_end = 6 * 60, 23 * 60
    # Unmet study minutes roll to later days (capped so we don't crush one day)
    carry_min = 0
    base_daily = day_targets[0] if day_targets else 180
    max_carry_in = max(60, int(round(base_daily * 0.5)))

    for i in range(max(1, horizon_days)):
        day = range_start + timedelta(days=i)
        key = _DAY_NAMES[day.weekday()]
        base_min = day_targets[i] if i < len(day_targets) else int(
            _parse_daily_focus_hours(goals) * 60 * load_scale
        )
        owed = base_min + carry_min
        # Aim for base + limited carry-in (don't schedule an impossible marathon)
        target_min = min(owed, base_min + max_carry_in)
        peaks = _peaks_for_weekday(export, key)

        busy: list[tuple[int, int]] = []
        for r in routines:
            if not isinstance(r, dict) or r.get("enabled") is False:
                continue
            days = r.get("days") or list(_DAY_NAMES)
            if key not in days:
                continue
            busy.append(_routine_interval_minutes(r))
        busy.extend(_busy_from_iso_blocks(busy_blocks, day))

        gaps = _free_gaps(busy, day_start=day_start, day_end=day_end, min_gap=30)
        packed = _pack_gaps_with_goals(
            gaps,
            target_min,
            slices,
            peaks,
            slice_offset=slice_i,
            min_chunk=30,
            preferred_chunk=50,
        )
        # Second pass with tinier chunks if still short of goal
        filled = sum(e - s for s, e, _t, c in packed if c != "break")
        if filled < target_min * 0.85:
            # Recompute busy including what we already packed
            busy2 = list(busy)
            for s, e, _t, c in packed:
                busy2.append((s, e))
            gaps2 = _free_gaps(busy2, day_start=day_start, day_end=day_end, min_gap=25)
            extra = _pack_gaps_with_goals(
                gaps2,
                target_min - filled,
                slices,
                peaks,
                slice_offset=slice_i + len(packed),
                min_chunk=25,
                preferred_chunk=45,
            )
            packed = packed + extra
            filled = sum(e - s for s, e, _t, c in packed if c != "break")

        # Carry unmet owed study into the next day
        carry_min = max(0, owed - filled)

        slice_i += max(1, len([p for p in packed if p[3] != "break"]))

        for start_m, end_m, title, cat in packed:
            if cat != "break" and _is_unproductive_label(title, cat):
                continue
            start_at, end_at = _local_block_iso(day, start_m, end_m)
            source = "break" if cat == "break" else "study"
            blocks.append(
                {
                    "title": title,
                    "category": cat,
                    "start_at": start_at,
                    "end_at": end_at,
                    "source": source,
                }
            )

    # Final safety: drop any unproductive study that slipped through
    blocks = [
        b
        for b in blocks
        if b.get("source") != "study"
        or not _is_unproductive_label(str(b.get("title") or ""), str(b.get("category") or ""))
    ]
    return _cascade_resolve_blocks(blocks)


_REVIEW_SYSTEM = """You are reviewing a draft study calendar.
Keep all routine blocks (source=routine) at their times unless clearly broken.
You may move/resize study blocks, rename them to match goals, and add short breaks.
Do NOT schedule entertainment/gaming as productive work.
Fill obvious empty gaps with goal work when daily focus target is unmet.
Return ONLY valid JSON: {"blocks":[...], "rationale":"..."} — no markdown.
Each block: title, category, start_at (ISO), end_at (ISO), source (routine|study|break).
"""


def _normalize_llm_blocks(raw_blocks: list[Any]) -> list[dict[str, Any]]:
    blocks: list[dict[str, Any]] = []
    for b in raw_blocks:
        if not isinstance(b, dict):
            continue
        title = str(b.get("title") or "Study block").strip()[:120]
        category = str(b.get("category") or "Study / Reading").strip()[:80]
        start_at = str(b.get("start_at") or "").strip()
        end_at = str(b.get("end_at") or "").strip()
        if not start_at or not end_at:
            continue
        source = str(b.get("source") or "study").strip().lower()
        if source not in ("routine", "study", "break", "existing"):
            source = "break" if category.lower() == "break" else "study"
        if source == "study" and _is_unproductive_label(title, category):
            continue
        blocks.append(
            {
                "title": title,
                "category": category,
                "start_at": start_at,
                "end_at": end_at,
                "source": source,
            }
        )
    return blocks


def propose_week_from_export(
    export: dict[str, Any],
    *,
    goals: str | None = None,
    week_start: date | None = None,
    horizon_days: int = 7,
    range_start: date | None = None,
    use_llm: bool = True,
    routines: list[dict[str, Any]] | None = None,
    mode: str | None = None,
    draft_blocks: list[dict[str, Any]] | None = None,
    busy_blocks: list[dict[str, Any]] | None = None,
    db: Any = None,
    user_id: int | None = None,
) -> dict[str, Any]:
    routines = routines or []
    busy_blocks = busy_blocks or []
    horizon_days = max(1, min(62, int(horizon_days or 7)))
    start = range_start or week_start or date.today()
    if week_start and not range_start and horizon_days == 7:
        start = _monday_of(week_start)
    # Never schedule into the past — clamp to local today.
    today = date.today()
    if start < today:
        start = today
    goals = (
        goals
        or "AI/ML and Scaler completion — protect deep work, no entertainment blocks."
    ).strip()

    # Resolve mode: review | smart | full
    resolved = (mode or "").strip().lower()
    if not resolved:
        if draft_blocks:
            resolved = "review"
        elif use_llm:
            resolved = "full"
        else:
            resolved = "smart"

    slim = {
        "range": export.get("range"),
        "summary": export.get("summary"),
        "weekday_patterns": export.get("weekday_patterns"),
        "suggested_timetable_hints": export.get("suggested_timetable_hints"),
        "policy_snapshot": export.get("policy_snapshot"),
        "routines": routines[:40],
    }
    range_end = start + timedelta(days=horizon_days - 1)
    used_llm = False
    rationale = ""
    blocks: list[dict[str, Any]] = []
    load_scale, avg_adh = _adherence_load_scale(export)
    sleep_scale, sleep_meta = 1.0, None
    if db is not None and user_id is not None:
        try:
            from backend.wearables.ingest_service import sleep_load_scale_for_user

            sleep_scale, sleep_meta = sleep_load_scale_for_user(db, int(user_id))
        except Exception:
            sleep_scale, sleep_meta = 1.0, None
    load_scale = min(float(load_scale or 1.0), float(sleep_scale or 1.0))
    stated_daily_h = _parse_daily_focus_hours(goals)
    scaled_daily_h = round(stated_daily_h * load_scale, 2)

    def _smart_blocks() -> list[dict[str, Any]]:
        return _fallback_blocks(
            export,
            start,
            horizon_days,
            routines,
            goals,
            busy_blocks=busy_blocks,
            load_scale=load_scale,
        )

    def _smart_rationale(blks: list[dict[str, Any]], prefix: str = "Smart gap-fill") -> str:
        n_r = sum(1 for b in blks if b.get("source") == "routine")
        n_b = sum(1 for b in blks if b.get("source") == "break")
        n_s = sum(1 for b in blks if b.get("source") == "study")
        study_min = 0
        for b in blks:
            if b.get("source") != "study":
                continue
            try:
                from datetime import datetime as _dt

                study_min += int(
                    (_dt.fromisoformat(b["end_at"]) - _dt.fromisoformat(b["start_at"])).total_seconds()
                    // 60
                )
            except Exception:
                pass
        target_total = int(round(scaled_daily_h * 60 * horizon_days))
        short = max(0, target_total - study_min)
        load_note = ""
        if load_scale < 1.0 and avg_adh is not None:
            load_note = (
                f"; load {int(load_scale * 100)}% of {stated_daily_h:g}h goal "
                f"(recent adherence ~{avg_adh:.0f}%)"
            )
        elif load_scale < 1.0 and sleep_meta and sleep_meta.get("sleep_hours") is not None:
            load_note = (
                f"; load {int(load_scale * 100)}% of {stated_daily_h:g}h goal "
                f"(sleep {sleep_meta['sleep_hours']}h soft)"
            )
        elif load_scale < 1.0:
            load_note = f"; load {int(load_scale * 100)}% of {stated_daily_h:g}h goal"
        short_note = f"; short {short}m vs target" if short >= 20 else ""
        return (
            f"{prefix} — ~50m chunks + breaks; aiming {scaled_daily_h:g}h study/day"
            f"{load_note}; planned {study_min / 60:.1f}h study "
            f"({n_s} blocks, {n_b} breaks, {n_r} routines){short_note}"
            + ("" if routines else " (no enabled routines)")
            + "."
        )

    if resolved == "smart":
        blocks = _smart_blocks()
        rationale = _smart_rationale(blocks)

    elif resolved == "review":
        draft = draft_blocks or _smart_blocks()
        if not draft_blocks:
            # auto-build smart draft then review
            pass
        prompt = (
            f"{_REVIEW_SYSTEM}\n\n"
            f"Plan range: {start.isoformat()} through {range_end.isoformat()} "
            f"({horizon_days} day(s)).\n"
            f"User goals: {goals}\n\n"
            f"Draft blocks JSON:\n{json.dumps(draft[:120], indent=2)[:12000]}\n\n"
            f"Tracker context:\n{json.dumps(slim, indent=2)[:6000]}\n\n"
            f"Respond with improved JSON like:\n{json.dumps(_SCHEMA_HINT, indent=2)}"
        )
        try:
            text = ollama_generate(prompt, task="planner_propose", timeout=90.0)
            if not text:
                raise ValueError("empty LLM response")
            data = _extract_json(text)
            raw = data.get("blocks") or []
            if not isinstance(raw, list) or not raw:
                raise ValueError("review returned no blocks")
            blocks = _normalize_llm_blocks(raw)
            rationale = str(data.get("rationale") or "AI reviewed draft plan.").strip()
            used_llm = True
        except Exception as e:
            log.warning("planner review LLM failed, keeping draft: %s", e)
            blocks = list(draft)
            rationale = f"AI review unavailable — kept smart draft. ({e})"

    else:  # full AI from scratch
        prompt = (
            f"{_SYSTEM}\n\n"
            f"Plan range: {start.isoformat()} through {range_end.isoformat()} "
            f"({horizon_days} day(s)).\n"
            f"User goals: {goals}\n\n"
            f"Context JSON:\n{json.dumps(slim, indent=2)[:14000]}\n\n"
            f"Respond with JSON like:\n{json.dumps(_SCHEMA_HINT, indent=2)}"
        )
        try:
            text = ollama_generate(prompt, task="planner_propose", timeout=90.0)
            if not text:
                raise ValueError("empty LLM response")
            data = _extract_json(text)
            raw = data.get("blocks") or []
            if not isinstance(raw, list):
                raise ValueError("blocks must be a list")
            blocks = _normalize_llm_blocks(raw)
            rationale = str(data.get("rationale") or "").strip()
            used_llm = True
        except Exception as e:
            log.warning("planner_propose LLM failed, using smart gap-fill: %s", e)
            blocks = _smart_blocks()
            rationale = _smart_rationale(blocks, prefix="LLM unavailable — smart gap-fill")

    if not blocks:
        blocks = _smart_blocks()
        rationale = rationale or _smart_rationale(blocks, prefix="Empty result — smart gap-fill")

    blocks = _cascade_resolve_blocks(blocks)

    return {
        "week_start": start.isoformat(),
        "range_start": start.isoformat(),
        "horizon_days": horizon_days,
        "blocks": blocks,
        "rationale": rationale,
        "used_llm": used_llm,
        "goals": goals,
        "mode": resolved,
        "load_scale": load_scale,
        "sleep_load": sleep_meta,
        "stated_daily_hours": stated_daily_h,
        "scaled_daily_hours": scaled_daily_h,
    }
