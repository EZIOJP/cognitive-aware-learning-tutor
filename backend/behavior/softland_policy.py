"""SoftLand policy store — Phase 2 SoT at data/productivity/behavior/softland_policy.json.

C++ Productivity owns this file long-term. Python writers/migrator land first.
Never sets hard_block_armed. SoftLand decide in C++ is out of scope here.
"""

from __future__ import annotations

import json
import re
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from backend.paths import BEHAVIOR_DIR

_PATH = BEHAVIOR_DIR / "softland_policy.json"
_LEGACY_SITE = BEHAVIOR_DIR / "softland_site_rules.json"
_LEGACY_SCHEDULES = BEHAVIOR_DIR / "gate_schedules.json"

_HOST_RE = re.compile(r"^[a-z0-9]([a-z0-9.-]*[a-z0-9])?\.[a-z]{2,}$", re.I)

_MODE_FLAG_KEYS = (
    "block_watch_sites",
    "block_porn",
    "block_social",
    "block_keywords",
    "block_other",
    "strict_allowlist",
)

_DEFAULT_MODE_STUDY = {
    "block_watch_sites": True,
    "block_porn": True,
    "block_social": True,
    "block_keywords": True,
    "block_other": True,
    "strict_allowlist": True,
}

_DEFAULT_MODE_FREE = {
    "block_watch_sites": False,
    "block_porn": True,
    "block_social": False,
    "block_keywords": True,
    "block_other": False,
    "strict_allowlist": False,
}

_DEFAULT_WINDOWS: list[dict[str, Any]] = [
    {
        "id": "weekday-focus",
        "label": "Weekday focus",
        "days": [0, 1, 2, 3, 4],
        "start": "09:00",
        "end": "18:00",
        "mode": "study",
    },
    {
        "id": "evening-free",
        "label": "Evening free",
        "days": [0, 1, 2, 3, 4, 5, 6],
        "start": "22:00",
        "end": "06:00",
        "mode": "free",
    },
]


def softland_policy_path() -> Path:
    return _PATH


def default_softland_policy() -> dict[str, Any]:
    return {
        "schema_version": 1,
        "updated_at": None,
        "softland_enabled": False,
        "site_rules": {
            "allow_extra": [],
            "watch_extra": [],
            "block_extra": [],
        },
        "schedules": {
            "enabled": False,
            "windows": deepcopy(_DEFAULT_WINDOWS),
        },
        "runtime": {
            "free_until": None,
            "free_after_hm": None,
            "incubation_until": None,
            "day_pass": {
                "date": None,
                "spent": False,
                "remaining_seconds": 0,
            },
            "reward_day_active": False,
            "earned_ledger_seconds": 0,
        },
        "goals": {
            "daily_focus_minutes": 0,
            "goal_met": False,
            "bible_done": False,
            "plan_confirmed_for_date": None,
            "plan_confirmed": False,
        },
        "mode_flags": {
            "study": dict(_DEFAULT_MODE_STUDY),
            "free": dict(_DEFAULT_MODE_FREE),
        },
    }


def _clean_domains(raw: Any) -> list[str]:
    if not isinstance(raw, list):
        return []
    out: list[str] = []
    seen: set[str] = set()
    for item in raw:
        s = str(item or "").strip().lower().removeprefix("https://").removeprefix("http://")
        s = s.split("/")[0].removeprefix("www.")
        if not s or s in seen:
            continue
        if not _HOST_RE.match(s) and "." not in s:
            continue
        seen.add(s)
        out.append(s)
    return out


def _clean_windows(raw: Any) -> list[dict[str, Any]]:
    if not isinstance(raw, list):
        return deepcopy(_DEFAULT_WINDOWS)
    cleaned: list[dict[str, Any]] = []
    for i, w in enumerate(raw):
        if not isinstance(w, dict):
            continue
        mode = str(w.get("mode") or "study").strip().lower()
        if mode not in ("study", "free", "planning", "bible"):
            mode = "study"
        days_raw = w.get("days") or []
        days = [int(d) for d in days_raw if isinstance(d, (int, float)) and 0 <= int(d) <= 6]
        cleaned.append({
            "id": str(w.get("id") or f"win-{i}"),
            "label": str(w.get("label") or f"Window {i + 1}")[:64],
            "days": days or [0, 1, 2, 3, 4],
            "start": str(w.get("start") or "09:00")[:5],
            "end": str(w.get("end") or "17:00")[:5],
            "mode": mode,
        })
    return cleaned or deepcopy(_DEFAULT_WINDOWS)


def _clean_mode_flags(raw: Any) -> dict[str, Any]:
    out = {
        "study": dict(_DEFAULT_MODE_STUDY),
        "free": dict(_DEFAULT_MODE_FREE),
    }
    if not isinstance(raw, dict):
        return out
    for mode, defaults in (("study", _DEFAULT_MODE_STUDY), ("free", _DEFAULT_MODE_FREE)):
        src = raw.get(mode)
        if not isinstance(src, dict):
            continue
        for k in _MODE_FLAG_KEYS:
            if k in src:
                out[mode][k] = bool(src[k])
    for mode in ("planning", "bible"):
        src = raw.get(mode)
        if isinstance(src, dict):
            flags = dict(_DEFAULT_MODE_STUDY)
            for k in _MODE_FLAG_KEYS:
                if k in src:
                    flags[k] = bool(src[k])
            out[mode] = flags
    return out


def _now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def normalize_policy(raw: dict[str, Any] | None) -> dict[str, Any]:
    base = default_softland_policy()
    if not isinstance(raw, dict):
        return base

    base["schema_version"] = int(raw.get("schema_version") or 1)
    base["updated_at"] = raw.get("updated_at")
    base["softland_enabled"] = bool(raw.get("softland_enabled"))

    sr = raw.get("site_rules") if isinstance(raw.get("site_rules"), dict) else {}
    base["site_rules"] = {
        "allow_extra": _clean_domains(sr.get("allow_extra")),
        "watch_extra": _clean_domains(sr.get("watch_extra")),
        "block_extra": _clean_domains(sr.get("block_extra")),
    }

    sched = raw.get("schedules") if isinstance(raw.get("schedules"), dict) else {}
    base["schedules"] = {
        "enabled": bool(sched.get("enabled")),
        "windows": _clean_windows(sched.get("windows")),
    }

    rt = raw.get("runtime") if isinstance(raw.get("runtime"), dict) else {}
    dp = rt.get("day_pass") if isinstance(rt.get("day_pass"), dict) else {}
    try:
        rem = int(dp.get("remaining_seconds") or 0)
    except (TypeError, ValueError):
        rem = 0
    try:
        earned = int(rt.get("earned_ledger_seconds") or 0)
    except (TypeError, ValueError):
        earned = 0
    free_after = rt.get("free_after_hm")
    if free_after is not None:
        free_after = str(free_after)[:5] or None
    base["runtime"] = {
        "free_until": rt.get("free_until"),
        "free_after_hm": free_after,
        "incubation_until": rt.get("incubation_until"),
        "day_pass": {
            "date": dp.get("date"),
            "spent": bool(dp.get("spent")),
            "remaining_seconds": max(0, rem),
        },
        "reward_day_active": bool(rt.get("reward_day_active")),
        "earned_ledger_seconds": max(0, earned),
    }

    goals = raw.get("goals") if isinstance(raw.get("goals"), dict) else {}
    try:
        daily = int(goals.get("daily_focus_minutes") or 0)
    except (TypeError, ValueError):
        daily = 0
    base["goals"] = {
        "daily_focus_minutes": max(0, daily),
        "goal_met": bool(goals.get("goal_met")),
        "bible_done": bool(goals.get("bible_done")),
        "plan_confirmed_for_date": goals.get("plan_confirmed_for_date"),
        "plan_confirmed": bool(goals.get("plan_confirmed")),
    }

    base["mode_flags"] = _clean_mode_flags(raw.get("mode_flags"))
    return base


def _read_json(path: Path) -> dict[str, Any] | None:
    try:
        if path.is_file():
            raw = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                return raw
    except Exception:
        pass
    return None


def _read_softland_enabled_from_sqlite() -> bool | None:
    try:
        from backend.db.base import SessionLocal
        from backend.models import ProductivityPolicy

        db = SessionLocal()
        try:
            row = db.query(ProductivityPolicy).order_by(ProductivityPolicy.id.asc()).first()
            if row is None:
                return None
            return bool(getattr(row, "hard_block_enabled", False))
        finally:
            db.close()
    except Exception:
        return None


def migrate_from_legacy(*, force: bool = False) -> dict[str, Any]:
    """One-shot: site rules + schedules + SoftLand enable → softland_policy.json."""
    if _PATH.is_file() and not force:
        return load_softland_policy()

    data = default_softland_policy()

    legacy_site = _read_json(_LEGACY_SITE)
    if legacy_site:
        data["site_rules"] = {
            "allow_extra": _clean_domains(legacy_site.get("allow_extra")),
            "watch_extra": _clean_domains(legacy_site.get("watch_extra")),
            "block_extra": _clean_domains(legacy_site.get("block_extra")),
        }

    legacy_sched = _read_json(_LEGACY_SCHEDULES)
    if legacy_sched:
        data["schedules"] = {
            "enabled": bool(legacy_sched.get("enabled")),
            "windows": _clean_windows(legacy_sched.get("windows")),
        }

    enabled = _read_softland_enabled_from_sqlite()
    if enabled is not None:
        data["softland_enabled"] = enabled

    return save_softland_policy(data, sync_legacy=True, mirror_incubation=True)


def load_softland_policy(*, migrate_if_missing: bool = True) -> dict[str, Any]:
    if not _PATH.is_file():
        if migrate_if_missing:
            return migrate_from_legacy()
        return default_softland_policy()
    raw = _read_json(_PATH)
    return normalize_policy(raw)


def _sync_legacy_files(data: dict[str, Any]) -> None:
    """Dual-write legacy JSON so older readers keep working during Phase 2."""
    try:
        _LEGACY_SITE.parent.mkdir(parents=True, exist_ok=True)
        _LEGACY_SITE.write_text(
            json.dumps(data.get("site_rules") or {}, indent=2) + "\n",
            encoding="utf-8",
        )
    except Exception:
        pass
    try:
        _LEGACY_SCHEDULES.write_text(
            json.dumps(data.get("schedules") or {}, indent=2) + "\n",
            encoding="utf-8",
        )
    except Exception:
        pass


def _mirror_incubation_to_enforcer(incubation_until: Any) -> None:
    """SoftLand store is source; mirror incubation_active for kill loop. Never Arms."""
    active = False
    if incubation_until:
        try:
            until = datetime.fromisoformat(str(incubation_until).replace("Z", "+00:00"))
            now = datetime.now(timezone.utc).astimezone()
            if until.tzinfo is None:
                until = until.replace(tzinfo=now.tzinfo)
            active = until > now
        except Exception:
            active = bool(incubation_until)

    try:
        from backend.behavior.enforcer_files import read_policy_file, write_policy_file

        existing = read_policy_file() or {}
        if not existing:
            return
        write_policy_file(
            hard_block_armed=bool(existing.get("hard_block_armed")),
            gate_locked=bool(existing.get("gate_locked")),
            incubation_active=active,
            exes=list(existing.get("exes") or []),
            note=str(existing.get("note") or "softland_incubation_mirror")[:120],
            preserve_lock_fields=True,
        )
    except Exception:
        pass


def save_softland_policy(
    payload: dict[str, Any],
    *,
    sync_legacy: bool = True,
    mirror_incubation: bool = True,
) -> dict[str, Any]:
    data = normalize_policy(payload)
    # SoftLand must never arm OS kills — strip any accidental keys.
    data.pop("hard_block_armed", None)
    data["updated_at"] = _now_iso()
    data["schema_version"] = 1

    _PATH.parent.mkdir(parents=True, exist_ok=True)
    _PATH.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")

    if sync_legacy:
        _sync_legacy_files(data)
    if mirror_incubation:
        _mirror_incubation_to_enforcer((data.get("runtime") or {}).get("incubation_until"))
    return data


def patch_softland_policy(patch: dict[str, Any]) -> dict[str, Any]:
    """Deep-merge top-level sections from patch into current SoT."""
    current = load_softland_policy()
    if not isinstance(patch, dict):
        return current

    if "softland_enabled" in patch:
        current["softland_enabled"] = bool(patch["softland_enabled"])

    if isinstance(patch.get("site_rules"), dict):
        sr = dict(current["site_rules"])
        for k in ("allow_extra", "watch_extra", "block_extra"):
            if k in patch["site_rules"]:
                sr[k] = patch["site_rules"][k]
        current["site_rules"] = sr

    if isinstance(patch.get("schedules"), dict):
        sch = dict(current["schedules"])
        if "enabled" in patch["schedules"]:
            sch["enabled"] = patch["schedules"]["enabled"]
        if "windows" in patch["schedules"]:
            sch["windows"] = patch["schedules"]["windows"]
        current["schedules"] = sch

    if isinstance(patch.get("runtime"), dict):
        rt = dict(current["runtime"])
        for k in ("free_until", "free_after_hm", "incubation_until", "reward_day_active", "earned_ledger_seconds"):
            if k in patch["runtime"]:
                rt[k] = patch["runtime"][k]
        if isinstance(patch["runtime"].get("day_pass"), dict):
            dp = dict(rt.get("day_pass") or {})
            dp.update(patch["runtime"]["day_pass"])
            rt["day_pass"] = dp
        current["runtime"] = rt

    if isinstance(patch.get("goals"), dict):
        goals = dict(current["goals"])
        goals.update(patch["goals"])
        current["goals"] = goals

    if isinstance(patch.get("mode_flags"), dict):
        current["mode_flags"] = patch["mode_flags"]

    return save_softland_policy(current)


def set_softland_enabled(enabled: bool) -> dict[str, Any]:
    return patch_softland_policy({"softland_enabled": bool(enabled)})


def site_rules_from_policy() -> dict[str, list[str]]:
    p = load_softland_policy()
    return dict(p.get("site_rules") or {})


def schedules_from_policy() -> dict[str, Any]:
    p = load_softland_policy()
    return dict(p.get("schedules") or {"enabled": False, "windows": []})


def softland_enabled_from_policy() -> bool:
    return bool(load_softland_policy().get("softland_enabled"))
