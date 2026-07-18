"""Distraction hard-block until daily productive goal (games + custom exes)."""

from __future__ import annotations

import logging
import os
from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

log = logging.getLogger("calt.distraction_gate")

# Seed list — common launchers / clients (user can extend via hard_block_exes).
DEFAULT_HARD_BLOCK_EXES: list[str] = [
    "steam.exe",
    "steamwebhelper.exe",
    "steamservice.exe",
    "start_protected_game.exe",
    "gameoverlayui.exe",
    "epicgameslauncher.exe",
    "epicwebhelper.exe",
    "galaxyclient.exe",
    "battle.net.exe",
    "riotclientservices.exe",
    "leagueclient.exe",
    "leagueclientux.exe",
    "valorant.exe",
    "fortniteclient-win64-shipping.exe",
    "minecraft.exe",
    "robloxplayerbeta.exe",
]

# Path fragments that mean "this process is a Steam/Epic game install"
_GAME_PATH_MARKERS: tuple[str, ...] = (
    "\\steam\\steamapps\\common\\",
    "\\steamapps\\common\\",
    "\\steam\\steamapps\\workshop\\",
    "\\epic games\\",
    "\\epicgames\\",
    "\\riot games\\",
    "\\xboxgames\\",
)

_STEAM_NAME_PREFIXES: tuple[str, ...] = (
    "steam",
    "gameoverlay",
    "start_protected_game",
)

# Never kill these even if listed (safety).
PROTECTED_EXES: frozenset[str] = frozenset(
    {
        "explorer.exe",
        "dwm.exe",
        "winlogon.exe",
        "csrss.exe",
        "services.exe",
        "lsass.exe",
        "svchost.exe",
        "system",
        "system idle process",
        "python.exe",
        "pythonw.exe",
        "cursor.exe",
        "code.exe",
        "powershell.exe",
        "pwsh.exe",
        "cmd.exe",
        "windows terminal.exe",
        "windowsterminal.exe",
        "conhost.exe",
        "taskmgr.exe",
        "searchhost.exe",
        "shellexperiencehost.exe",
        "applicationframehost.exe",
        "textinputhost.exe",
        "runtimebroker.exe",
        "sihost.exe",
        "fontdrvhost.exe",
    }
)


def normalize_exe(exe: str | None) -> str:
    name = (exe or "").strip().lower()
    if "\\" in name or "/" in name:
        name = name.replace("\\", "/").rsplit("/", 1)[-1]
    return name


def hard_block_exe_set(policy: dict[str, Any]) -> set[str]:
    out: set[str] = set()
    for item in policy.get("hard_block_exes") or []:
        n = normalize_exe(str(item))
        if n:
            out.add(n)
    return out


def is_protected_exe(exe: str | None) -> bool:
    return normalize_exe(exe) in PROTECTED_EXES


def process_exe_path(pid: int) -> str:
    if pid <= 0:
        return ""
    try:
        import psutil

        return (psutil.Process(pid).exe() or "").lower()
    except Exception:  # noqa: BLE001
        return ""


def looks_like_game_process(exe: str | None, pid: int = 0) -> bool:
    """True for Steam/Epic/Riot launchers and games running from game install folders."""
    name = normalize_exe(exe)
    if not name or name in PROTECTED_EXES:
        return False
    if name.endswith(".exe"):
        stem = name[:-4]
    else:
        stem = name
    for prefix in _STEAM_NAME_PREFIXES:
        if stem == prefix or stem.startswith(prefix):
            return True
    path = process_exe_path(pid) if pid else ""
    if path:
        for marker in _GAME_PATH_MARKERS:
            if marker in path:
                return True
        # Steam client folder itself (not Common Files noise)
        if "\\steam\\" in path and "steamapps" not in path:
            if name.startswith("steam") or name in {
                "start_protected_game.exe",
                "gameoverlayui.exe",
            }:
                return True
    return False


def should_hard_block(
    exe: str | None,
    category: str | None,
    policy: dict[str, Any],
    *,
    pid: int = 0,
) -> bool:
    """True if this foreground app should be killed while the gate is locked."""
    if not policy.get("hard_block_enabled"):
        return False
    name = normalize_exe(exe)
    if not name or name in PROTECTED_EXES:
        return False
    if name in hard_block_exe_set(policy):
        return True
    if policy.get("hard_block_gaming", True):
        cat = (category or "").strip()
        if cat.lower() == "gaming" or cat == "Gaming":
            return True
        # Steam launches real games as start_protected_game.exe / GameName.exe
        # under steamapps — those often classify as Other, not Gaming.
        if looks_like_game_process(exe, pid):
            return True
    return False


def list_blockable_pids(policy: dict[str, Any]) -> list[tuple[int, str]]:
    """Scan running processes for hard-block targets (not only foreground)."""
    if not policy.get("hard_block_enabled"):
        return []
    out: list[tuple[int, str]] = []
    seen: set[int] = set()
    try:
        import psutil
    except ImportError:
        return out
    for proc in psutil.process_iter(["pid", "name"]):
        try:
            pid = int(proc.info.get("pid") or 0)
            name = str(proc.info.get("name") or "")
        except (TypeError, ValueError):
            continue
        if pid <= 0 or pid in seen or is_protected_exe(name) or pid == os.getpid():
            continue
        if should_hard_block(name, None, policy, pid=pid):
            seen.add(pid)
            out.append((pid, name))
    return out


def terminate_blocked_process(pid: int, *, exe: str = "") -> bool:
    """Best-effort terminate. Returns True if a kill was attempted successfully."""
    if pid <= 0:
        return False
    if pid == os.getpid():
        return False
    if is_protected_exe(exe):
        log.info("Skip kill protected exe=%s pid=%s", exe, pid)
        return False
    try:
        import psutil

        proc = psutil.Process(pid)
        try:
            pname = proc.name()
        except (psutil.Error, OSError):
            pname = exe
        if is_protected_exe(pname):
            return False
        if normalize_exe(pname) in {"python.exe", "pythonw.exe"}:
            return False
        # Children first (Steam often leaves game child running)
        try:
            kids = proc.children(recursive=True)
        except (psutil.Error, OSError):
            kids = []
        for child in kids:
            try:
                if is_protected_exe(child.name()):
                    continue
                child.terminate()
            except (psutil.Error, OSError):
                pass
        proc.terminate()
        try:
            proc.wait(timeout=2)
        except (psutil.TimeoutExpired, psutil.Error):
            try:
                proc.kill()
            except (psutil.Error, OSError) as exc:
                log.warning("kill failed pid=%s: %s — trying taskkill", pid, exc)
                try:
                    import subprocess

                    subprocess.run(
                        ["taskkill", "/F", "/T", "/PID", str(pid)],
                        capture_output=True,
                        timeout=5,
                        check=False,
                    )
                except Exception as exc2:  # noqa: BLE001
                    log.warning("taskkill failed pid=%s: %s", pid, exc2)
                    return False
        log.info("Hard-blocked pid=%s exe=%s", pid, pname or exe)
        return True
    except Exception as exc:  # noqa: BLE001
        log.warning("terminate_blocked_process failed pid=%s: %s", pid, exc)
        return False


def compute_distraction_gate(db: Session, user_id: int) -> dict[str, Any]:
    """Locked until productive minutes today >= daily_goal_minutes."""
    from backend.behavior.category_scores import load_score_map
    from backend.behavior.productivity_policy import load_policy_dict, resolve_session_score
    from backend.models.timetable import TrackedSession
    from backend.planner.service import local_day_bounds_utc, local_tz

    policy = load_policy_dict(db, user_id)
    enabled = bool(policy.get("hard_block_enabled"))
    goal = max(1, int(policy.get("daily_goal_minutes") or 240))
    threshold = int(policy.get("threshold") or 60)

    day_date = datetime.now(local_tz()).date()
    start, end = local_day_bounds_utc(day_date)
    sessions = (
        db.query(TrackedSession)
        .filter(
            TrackedSession.user_id == user_id,
            TrackedSession.start_time < end,
            TrackedSession.end_time > start,
        )
        .all()
    )
    scores = load_score_map(db)

    def score_fn(sess):
        return resolve_session_score(sess, scores, policy)

    productive = 0
    for s in sessions:
        if not s.start_time or not s.end_time:
            continue
        if score_fn(s) < threshold:
            continue
        productive += int((s.end_time - s.start_time).total_seconds() // 60)

    unlocked = (not enabled) or (productive >= goal)
    remaining = max(0, goal - productive) if enabled else 0

    return {
        "enabled": enabled,
        "locked": bool(enabled and not unlocked),
        "unlocked": unlocked,
        "productive_minutes": productive,
        "daily_goal_minutes": goal,
        "remaining_minutes": remaining,
        "hard_block_gaming": bool(policy.get("hard_block_gaming", True)),
        "hard_block_exes": list(policy.get("hard_block_exes") or []),
        "day": day_date.isoformat(),
    }
