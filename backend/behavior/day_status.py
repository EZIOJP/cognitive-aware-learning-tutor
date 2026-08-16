"""Aggregate morning + browser mode + hard-block + tracker + wearables for mobile/watch."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from backend.paths import ROOT

_NOTIFY_STATE_PATH = ROOT / "data" / "behavior" / "day_status_notify.json"
_PENDING_MOBILE_PATH = ROOT / "data" / "behavior" / "pending_mobile_alerts.json"

_MODE_LABELS = {
    "bible": "Bible first",
    "planning": "Planning mode",
    "study": "Study mode",
    "free": "Free mode",
}

_NEXT_LABELS = {
    "bible": "Bible first",
    "plan": "Confirm today's plan",
    "open": "Day open",
}


def _read_json(path: Path) -> dict[str, Any]:
    try:
        if path.is_file():
            raw = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                return raw
    except Exception:
        pass
    return {}


def _write_json(path: Path, data: dict[str, Any]) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    except Exception:
        pass


def _wearables_snapshot() -> dict[str, Any]:
    path = ROOT / "data" / "wearables_last_sync.json"
    state = _read_json(path)
    if not state:
        return {"ok": False, "last_sync": None}
    return {
        "ok": True,
        "last_ingest_at": state.get("last_ingest_at"),
        "last_source": state.get("last_source"),
        "last_is_watch": bool(state.get("last_is_watch")),
        "last_wrote_life": bool(state.get("last_wrote_life")),
        "last_local_date": state.get("last_local_date"),
        "sleep_hours": state.get("last_sleep_hours"),
        "steps": state.get("last_steps"),
        "stand_hours": state.get("last_stand"),
        "sitting_min": state.get("last_sitting_min"),
        "stress": state.get("last_stress"),
        "hr": state.get("last_hr"),
        "last_event": state.get("last_event"),
    }


def _tracker_compact(db: Session, user_id: int) -> dict[str, Any]:
    from datetime import date

    from backend.behavior.tracker_status import count_tracker_processes, tracker_process_detail
    from backend.models.timetable import TrackedSession
    from backend.planner.service import iso_utc, local_day_bounds_utc
    from backend.timetable.tracker_query import tracker_user_ids

    proc = tracker_process_detail()
    today = date.today()
    start, end = local_day_bounds_utc(today)
    # Prefer solo owner ids when available
    try:
        from backend.models import User

        user = db.query(User).filter(User.id == user_id).first()
        user_ids = tracker_user_ids(db, user) if user else [user_id]
    except Exception:
        user_ids = [user_id]

    rows = (
        db.query(TrackedSession)
        .filter(
            TrackedSession.user_id.in_(user_ids),
            TrackedSession.source == "desktop_tracker",
            TrackedSession.start_time >= start,
            TrackedSession.start_time < end,
        )
        .all()
    )
    last_at = max((r.end_time for r in rows if r.end_time), default=None)
    alive = bool(proc.get("process_alive"))
    if not alive and last_at is not None:
        try:
            age = (datetime.now(timezone.utc) - last_at.astimezone(timezone.utc)).total_seconds()
            alive = age < 180
        except Exception:
            pass

    if alive:
        status = "running"
    elif last_at:
        status = "stale"
    else:
        status = "no_data"

    return {
        "alive": alive,
        "status": status,
        "last_event_at": iso_utc(last_at) if last_at else None,
        "sessions_today": len(rows),
        "process_alive": bool(proc.get("process_alive")),
        "checkpoint_age_s": proc.get("checkpoint_age_s"),
        "tracker_process_count": count_tracker_processes(),
    }


def _notify_payload(
    *,
    browser_mode: str | None,
    morning_next: str | None,
    hard_block_armed: bool,
    locked: bool,
) -> dict[str, Any]:
    mode = (browser_mode or "free").strip().lower()
    nxt = (morning_next or "open").strip().lower()
    title = _MODE_LABELS.get(mode, mode.replace("_", " ").title())
    if nxt in ("bible", "plan"):
        title = _NEXT_LABELS.get(nxt, title)
        body = (
            "Finish today's chapter before the day opens."
            if nxt == "bible"
            else "Review and confirm today's plan."
        )
    elif locked and hard_block_armed:
        body = "Hard-block locked — stay on productive work."
    elif hard_block_armed:
        body = f"Hard-block armed · mode {mode}."
    else:
        body = f"Day mode: {mode}."
    return {
        "title": title[:48],
        "body": body[:120],
        "browser_mode": mode,
        "morning_next": nxt,
        "hard_block_armed": hard_block_armed,
        "locked": locked,
    }


def _maybe_enqueue_mobile_alert(notify: dict[str, Any]) -> dict[str, Any] | None:
    """Enqueue a phone-local alert when mode/morning/arm fingerprint changes."""
    fingerprint = "|".join(
        [
            str(notify.get("browser_mode") or ""),
            str(notify.get("morning_next") or ""),
            "1" if notify.get("hard_block_armed") else "0",
            "1" if notify.get("locked") else "0",
        ]
    )
    prev = _read_json(_NOTIFY_STATE_PATH)
    if prev.get("fingerprint") == fingerprint:
        return None
    item = {
        **notify,
        "ts": datetime.now(timezone.utc).isoformat(),
        "fingerprint": fingerprint,
        "channel": "local",  # phone shows notification; Zepp mirrors via Android notify
    }
    pending = []
    try:
        if _PENDING_MOBILE_PATH.is_file():
            raw = json.loads(_PENDING_MOBILE_PATH.read_text(encoding="utf-8"))
            if isinstance(raw, list):
                pending = [x for x in raw if isinstance(x, dict)]
    except Exception:
        pending = []
    pending.append(item)
    pending = pending[-30:]
    try:
        _PENDING_MOBILE_PATH.parent.mkdir(parents=True, exist_ok=True)
        _PENDING_MOBILE_PATH.write_text(json.dumps(pending, indent=0), encoding="utf-8")
    except Exception:
        pass
    _write_json(
        _NOTIFY_STATE_PATH,
        {
            "fingerprint": fingerprint,
            "updated_at": item["ts"],
            "last_title": item.get("title"),
        },
    )
    return item


def peek_mobile_alerts() -> list[dict[str, Any]]:
    """Read pending alerts without draining."""
    try:
        if _PENDING_MOBILE_PATH.is_file():
            raw = json.loads(_PENDING_MOBILE_PATH.read_text(encoding="utf-8"))
            if isinstance(raw, list):
                return [x for x in raw if isinstance(x, dict)]
    except Exception:
        pass
    return []


def drain_mobile_alerts(*, max_items: int = 10) -> list[dict[str, Any]]:
    """Pop pending alerts for the Android app (local notification relay)."""
    items = peek_mobile_alerts()
    try:
        _PENDING_MOBILE_PATH.parent.mkdir(parents=True, exist_ok=True)
        _PENDING_MOBILE_PATH.write_text("[]", encoding="utf-8")
    except Exception:
        pass
    return items[: max(1, max_items)]


def build_checklist(morning: dict[str, Any]) -> list[dict[str, Any]]:
    nxt = (morning.get("next") or "open").strip().lower()
    return [
        {
            "id": "bible",
            "label": "Bible chapter",
            "done": bool(morning.get("bible_done")),
            "cta": morning.get("bible_url"),
            "active": nxt == "bible",
        },
        {
            "id": "plan",
            "label": "Confirm today's plan",
            "done": bool(morning.get("plan_done") or morning.get("plan_confirmed")),
            "cta": morning.get("plan_url"),
            "active": nxt == "plan",
        },
        {
            "id": "open",
            "label": "Day open",
            "done": nxt == "open",
            "cta": None,
            "active": nxt == "open",
        },
    ]


def build_day_status(db: Session, user_id: int, *, enqueue_notify: bool = True) -> dict[str, Any]:
    """Compact day snapshot for CALT Android + Amazfit notification relay."""
    from backend.behavior.distraction_gate import compute_distraction_gate

    gate = compute_distraction_gate(db, user_id)
    morning = gate.get("morning") or {}
    browser = gate.get("browser") or {}
    browser_mode = (
        gate.get("browser_mode")
        or browser.get("mode")
        or "free"
    )
    hard_block_armed = bool(gate.get("enabled"))
    locked = bool(gate.get("locked"))

    notify = _notify_payload(
        browser_mode=str(browser_mode),
        morning_next=str(morning.get("next") or "open"),
        hard_block_armed=hard_block_armed,
        locked=locked,
    )
    enqueued = _maybe_enqueue_mobile_alert(notify) if enqueue_notify else None

    tracker = _tracker_compact(db, user_id)
    wearables = _wearables_snapshot()
    suggested = morning.get("suggested_wake")

    return {
        "ok": True,
        "schema": 1,
        "day": gate.get("day") or morning.get("day"),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "morning": {
            "enabled": bool(morning.get("enabled")),
            "next": morning.get("next"),
            "bible_done": bool(morning.get("bible_done")),
            "plan_done": bool(morning.get("plan_done")),
            "plan_confirmed": bool(morning.get("plan_confirmed")),
            "blocks_today": morning.get("blocks_today"),
            "hint": morning.get("hint"),
            "bible_url": morning.get("bible_url"),
            "plan_url": morning.get("plan_url"),
            "suggested_wake": suggested,
            "rewards": morning.get("rewards"),
            "plan_window": morning.get("plan_window"),
        },
        "checklist": build_checklist(morning),
        "browser_mode": browser_mode,
        "browser_mode_label": _MODE_LABELS.get(str(browser_mode), str(browser_mode)),
        "hard_block": {
            "armed": hard_block_armed,
            "locked": locked,
            "unlocked": bool(gate.get("unlocked")),
            "productive_minutes": gate.get("productive_minutes"),
            "daily_goal_minutes": gate.get("daily_goal_minutes"),
            "remaining_minutes": gate.get("remaining_minutes"),
            "day_unlimited": bool(gate.get("day_unlimited")),
        },
        "tracker": tracker,
        "tracker_alive": bool(tracker.get("alive")),
        "wearables": wearables,
        "notify": notify,
        "alert_enqueued": bool(enqueued),
        "limits": {
            "watch_app": (
                "Zepp OS mini-program (packages/calt-zepp) syncs health + shows gate; "
                "it is not a full CALT install on the watch face."
            ),
            "alerts": (
                "Watch alerts come from Zepp notifications or Android notification mirror "
                "(phone shows local notify → watch if Zepp notification mirror is on)."
            ),
            "smart_alarm": (
                "CALT only suggests wake soft (morning.suggested_wake); "
                "hardware T-Rex smart alarm stays on-device."
            ),
            "hard_block_arm": (
                "Arm/disarm requires JWT via PUT /api/behavior/policy — "
                "do not expose wearable ingest key for policy writes."
            ),
        },
    }
