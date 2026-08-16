"""Proactive morning brief — canned only, once per calendar day.

Flag: ``data/voice_agent/morning_briefed_{YYYY-MM-DD}.json``

Triggers (callers):
  - Tracker gate refresh after 5am local (if morning next is bible/plan, or force path)
  - First voice chat open of the day
  - Chat ``/brief`` (force + fresh stats)

Never uses the LLM. Speaks short sequence with ``force=True`` so rate-limit
does not swallow the multi-line brief.
"""

from __future__ import annotations

import csv
import json
import logging
import threading
import time
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

from backend.paths import ROOT
from backend.planner.service import local_tz

log = logging.getLogger("calt.morning_brief")

_DIR = ROOT / "data" / "voice_agent"
_DATA_LOGS = ROOT / "data_logs"
_FOCUS_SCORE = 60  # align with default productivity threshold
_MORNING_HOUR_START = 5

_lock = threading.Lock()
_brief_thread: threading.Thread | None = None


def _today() -> date:
    return datetime.now(local_tz()).date()


def _flag_path(day: date | None = None) -> Path:
    d = day or _today()
    return _DIR / f"morning_briefed_{d.isoformat()}.json"


def was_briefed_today(day: date | None = None) -> bool:
    return _flag_path(day).is_file()


def mark_briefed(
    *,
    source: str = "auto",
    day: date | None = None,
    lines: list[str] | None = None,
) -> None:
    p = _flag_path(day)
    p.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "briefed_at": datetime.now(local_tz()).isoformat(),
        "source": source,
        "lines": list(lines or [])[:12],
    }
    p.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def clear_brief_flag(day: date | None = None) -> None:
    p = _flag_path(day)
    try:
        if p.is_file():
            p.unlink()
    except OSError:
        pass


def summarize_desktop_csv(day: date) -> dict[str, int]:
    """Lightweight yesterday/today stats from tracker CSV — no hub/DB required."""
    path = _DATA_LOGS / f"DSC_desktop_behavior_{day.isoformat()}.csv"
    focus_s = 0.0
    distracted_s = 0.0
    sessions = 0
    if not path.is_file():
        return {"focus_min": 0, "distracted_min": 0, "blocks": 0}
    try:
        with path.open(newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                try:
                    dur = float(row.get("duration_seconds") or 0)
                except ValueError:
                    dur = 0.0
                if dur < 2:
                    continue
                sessions += 1
                try:
                    score = int(float(row.get("productivity_score") or 0))
                except ValueError:
                    score = 0
                if score >= _FOCUS_SCORE:
                    focus_s += dur
                else:
                    distracted_s += dur
    except Exception as exc:  # noqa: BLE001
        log.debug("csv summarize failed %s: %s", path.name, exc)
        return {"focus_min": 0, "distracted_min": 0, "blocks": 0}
    return {
        "focus_min": int(focus_s // 60),
        "distracted_min": int(distracted_s // 60),
        "blocks": sessions,
    }


def stats_fmt(*, prefer_yesterday: bool = True) -> dict[str, Any]:
    """Placeholder values for templates. Prefer yesterday when briefing the morning."""
    today = _today()
    day = today - timedelta(days=1) if prefer_yesterday else today
    stats = summarize_desktop_csv(day)
    # Graceful: if yesterday empty, try today
    if prefer_yesterday and stats["focus_min"] == 0 and stats["blocks"] == 0:
        stats = summarize_desktop_csv(today)
    return stats


def _morning_context(user_id: int) -> dict[str, Any]:
    """Read gate morning.next / bible/plan flags. Soft-fail to unknowns."""
    out: dict[str, Any] = {
        "next": "open",
        "bible_done": False,
        "plan_done": False,
        "enabled": True,
    }
    try:
        from backend.behavior.distraction_gate import compute_distraction_gate
        from backend.db.session import SessionLocal

        db = SessionLocal()
        try:
            g = compute_distraction_gate(db, int(user_id))
        finally:
            db.close()
        m = g.get("morning") or {}
        out["next"] = str(m.get("next") or "open").strip().lower()
        out["bible_done"] = bool(m.get("bible_done"))
        out["plan_done"] = bool(m.get("plan_done") or m.get("plan_confirmed"))
        out["enabled"] = bool(m.get("enabled", True))
        out["productive_minutes"] = int(g.get("productive_minutes") or 0)
        out["auto_plan"] = m.get("auto_plan") if isinstance(m.get("auto_plan"), dict) else {}
    except Exception as exc:  # noqa: BLE001
        log.debug("morning context failed: %s", exc)
    return out


def build_brief_lines(user_id: int, *, include_stats: bool = True) -> list[str]:
    """Compose canned brief lines (no speak)."""
    from backend.behavior.voice_agent.dialogues import pick

    ctx = _morning_context(user_id)
    lines: list[str] = [pick("morning_greet")]

    nxt = ctx.get("next") or "open"
    if not ctx.get("bible_done") or nxt == "bible":
        lines.append(pick("morning_bible_nudge"))
    elif not ctx.get("plan_done") or nxt == "plan":
        auto = ctx.get("auto_plan") if isinstance(ctx.get("auto_plan"), dict) else {}
        if auto.get("drafted") and auto.get("titles"):
            lines.append(pick("plan_auto_drafted"))
        else:
            lines.append(pick("morning_plan_brief"))
        lines.append(pick("plan_confirm_prompt"))

    if include_stats:
        fmt = stats_fmt(prefer_yesterday=True)
        if fmt.get("blocks") or fmt.get("focus_min"):
            lines.append(pick("plan_from_yesterday", **fmt))
            # Optional second stats flavour if yesterday had data
            if fmt.get("focus_min", 0) > 0:
                lines.append(pick("productivity_stats_brief", **fmt))

    # Dedupe consecutive identical (unlikely) and cap length
    out: list[str] = []
    for ln in lines:
        ln = (ln or "").strip()
        if not ln:
            continue
        if out and out[-1] == ln:
            continue
        out.append(ln)
    return out[:5]


def _speak_sequence(lines: list[str], *, gap_s: float = 0.35) -> None:
    """Speak lines one after another — wait for each utterance (no overlap)."""
    from backend.behavior.gate_alerts import speak_alert_sync

    for i, ln in enumerate(lines):
        speak_alert_sync(ln, force=True)
        if i < len(lines) - 1 and gap_s > 0:
            time.sleep(gap_s)


def maybe_speak_morning_brief(
    user_id: int,
    *,
    force: bool = False,
    source: str = "auto",
    after_hour: int = _MORNING_HOUR_START,
    require_morning_gate: bool = False,
    async_speak: bool = True,
) -> list[str] | None:
    """Speak once-per-day morning brief if appropriate. Returns lines or None.

    ``force``: ignore once/day flag (e.g. ``/brief``).
    ``require_morning_gate``: only fire if morning.next is bible or plan
      (used by tracker poll so we don't brief when day already open — unless force).
    """
    global _brief_thread
    try:
        from backend.behavior.voice_agent import voice_runtime_allowed

        if not force and not voice_runtime_allowed():
            return None
    except Exception:  # noqa: BLE001
        pass
    hour = datetime.now(local_tz()).hour
    if not force and hour < after_hour:
        return None
    if not force and was_briefed_today():
        return None

    if require_morning_gate and not force:
        ctx = _morning_context(user_id)
        if (ctx.get("next") or "open") not in ("bible", "plan"):
            # Day already open — still allow first chat greet via force/chat path only
            return None

    lines = build_brief_lines(user_id, include_stats=True)
    if not lines:
        return None

    mark_briefed(source=source, lines=lines)

    def _run() -> None:
        try:
            _speak_sequence(lines)
        except Exception as exc:  # noqa: BLE001
            log.warning("morning brief speak failed: %s", exc)

    if async_speak:
        with _lock:
            if _brief_thread is not None and _brief_thread.is_alive():
                return lines
            _brief_thread = threading.Thread(
                target=_run, name="morning-brief", daemon=True
            )
            _brief_thread.start()
    else:
        _run()
    log.info("morning brief (%s): %s line(s)", source, len(lines))
    return lines


def maybe_chat_open_greet(user_id: int) -> list[str] | None:
    """On voice chat open: morning brief if not yet today; else rare idle check-in."""
    if not was_briefed_today():
        return maybe_speak_morning_brief(
            user_id, force=False, source="chat_open", require_morning_gate=False
        )
    # Rare idle — ~15% so it doesn't feel spammy on every reopen
    import random

    if random.random() > 0.15:
        return None
    from backend.behavior.voice_agent.dialogues import speak

    line = speak("idle_checkin", force=False)
    return [line] if line else None


def force_brief(user_id: int) -> list[str]:
    """``/brief`` — always speak fresh canned brief with live placeholders."""
    lines = build_brief_lines(user_id, include_stats=True)
    mark_briefed(source="brief_cmd", lines=lines)

    def _run() -> None:
        try:
            _speak_sequence(lines)
        except Exception as exc:  # noqa: BLE001
            log.warning("/brief speak failed: %s", exc)

    threading.Thread(target=_run, name="force-brief", daemon=True).start()
    return lines
