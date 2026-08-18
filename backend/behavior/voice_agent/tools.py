"""Allowlisted voice-agent tools.

Safe OS helpers (Windows-first): web_search, open_url, open_app, play_music,
media_play, volume_up/down/mute, set_volume, system_info — plus calendar,
memory, gate, and confirm-gated PC / hard-block tools.

No arbitrary shell (run_command intentionally absent).
"""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
import webbrowser
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import quote_plus, urlparse

from backend.behavior.voice_agent import memory as mem

log = logging.getLogger("desktop_tracker.voice_agent")

RISKY_TOOLS = frozenset(
    {
        "pc_lock",
        "pc_shutdown",
        "pc_sleep",
        "hard_block_arm",
        "hard_block_disarm",
    }
)

# Allowlisted app keys → launch targets (resolved at call time).
_APP_ALIASES: dict[str, tuple[str, ...]] = {
    "notepad": ("notepad.exe",),
    "explorer": ("explorer.exe",),
    "calc": ("calc.exe",),
    "calculator": ("calc.exe",),
    "msedge": ("msedge.exe",),
    "edge": ("msedge.exe",),
    "chrome": ("chrome.exe",),
    "spotify": ("spotify.exe",),
    "vscode": ("code.cmd", "code.exe"),
    "code": ("code.cmd", "code.exe"),
    "cursor": ("cursor.cmd", "Cursor.exe", "cursor.exe"),
}

TOOL_SPECS: list[dict[str, str]] = [
    {"name": "calendar_today", "desc": "List today's planner blocks"},
    {"name": "calendar_add", "desc": "Add planner block. args: title, duration_minutes?, start_iso?"},
    {"name": "memory_get", "desc": "Get saved facts. args: key? (omit for all)"},
    {"name": "memory_set", "desc": "Save a fact. args: key, value"},
    {"name": "gate_status", "desc": "Read distraction/morning gate status"},
    {"name": "web_search", "desc": "Open browser to DuckDuckGo search. args: query"},
    {"name": "open_url", "desc": "Open http(s) URL in browser. args: url"},
    {
        "name": "open_app",
        "desc": "Launch allowlisted app. args: name "
        "(notepad|explorer|calc|msedge|chrome|edge|spotify|vscode|cursor)",
    },
    {
        "name": "play_music",
        "desc": "Open Spotify search/URI or Music folder. args: query? or uri?",
    },
    {"name": "media_play", "desc": "Send Windows media Play/Pause key"},
    {"name": "volume_up", "desc": "Raise system volume (media key)"},
    {"name": "volume_down", "desc": "Lower system volume (media key)"},
    {"name": "volume_mute", "desc": "Toggle mute (media key)"},
    {"name": "set_volume", "desc": "Set volume 0–100 if pycaw/nircmd available. args: level"},
    {"name": "system_info", "desc": "Local time, date, battery, distraction gate"},
    {
        "name": "start_calt_stack",
        "desc": "Launch run.bat (API+Vite) from the tracker — works when Web/API are down",
    },
    {"name": "pc_lock", "desc": "Lock the Windows workstation (needs confirm)"},
    {"name": "pc_shutdown", "desc": "Schedule Windows shutdown in 30s (needs confirm)"},
    {"name": "pc_sleep", "desc": "Put PC to sleep (needs confirm)"},
    {"name": "hard_block_arm", "desc": "Enable game hard-block policy (needs confirm)"},
    {"name": "hard_block_disarm", "desc": "Disable game hard-block policy (needs confirm)"},
]


def is_risky(name: str) -> bool:
    return (name or "").strip() in RISKY_TOOLS


def tools_prompt_block() -> str:
    lines = ["Available tools (call at most one per turn when needed):"]
    for t in TOOL_SPECS:
        risk = " [RISKY-CONFIRM]" if t["name"] in RISKY_TOOLS else ""
        lines.append(f"- {t['name']}{risk}: {t['desc']}")
    lines.append(
        'To call a tool, output exactly one line: TOOL <name> <json_object>\n'
        "Then wait. For normal chat, reply in plain sentences only."
    )
    return "\n".join(lines)


def _local_tz():
    from backend.planner.service import local_tz

    return local_tz()


def _calendar_today(user_id: int) -> str:
    from backend.db.session import SessionLocal
    from backend.models.planner import PlannerBlock
    from backend.planner.service import local_day_bounds_utc, serialize_block

    day = datetime.now(_local_tz()).date()
    start, end = local_day_bounds_utc(day)
    db = SessionLocal()
    try:
        rows = (
            db.query(PlannerBlock)
            .filter(
                PlannerBlock.user_id == user_id,
                PlannerBlock.start_at < end,
                PlannerBlock.end_at > start,
            )
            .order_by(PlannerBlock.start_at)
            .all()
        )
        if not rows:
            return "No planner blocks today."
        parts = []
        for b in rows:
            s = serialize_block(b)
            parts.append(
                f"- {s.get('title')} | {s.get('start_at')} → {s.get('end_at')} | {s.get('status')}"
            )
        return "Today's plan:\n" + "\n".join(parts)
    finally:
        db.close()


def _calendar_add(user_id: int, args: dict[str, Any]) -> str:
    from backend.db.session import SessionLocal
    from backend.models.planner import PlannerBlock

    title = str(args.get("title") or "").strip()
    if not title:
        return "error: title required"
    try:
        duration = max(5, int(args.get("duration_minutes") or 30))
    except (TypeError, ValueError):
        duration = 30
    start_iso = args.get("start_iso")
    tz = _local_tz()
    if start_iso:
        start = datetime.fromisoformat(str(start_iso).replace("Z", "+00:00"))
        if start.tzinfo is None:
            start = start.replace(tzinfo=tz)
    else:
        start = datetime.now(tz) + timedelta(minutes=5)
        start = start.replace(second=0, microsecond=0)
    end = start + timedelta(minutes=duration)
    db = SessionLocal()
    try:
        block = PlannerBlock(
            user_id=user_id,
            title=title,
            category=str(args.get("category") or "personal"),
            start_at=start,
            end_at=end,
            planned_minutes=duration,
            remaining_minutes=duration,
            status="scheduled",
        )
        db.add(block)
        db.commit()
        db.refresh(block)
        return f"Added '{title}' for {format_hours_mins(duration)} starting {start.isoformat()}"
    finally:
        db.close()


def _gate_status(user_id: int) -> str:
    try:
        from backend.behavior.distraction_gate import compute_distraction_gate
        from backend.db.session import SessionLocal

        db = SessionLocal()
        try:
            g = compute_distraction_gate(db, user_id)
        finally:
            db.close()
    except Exception as exc:  # noqa: BLE001
        return f"Gate unavailable ({exc}). Tracker voice/TTS still works locally."
    m = g.get("morning") or {}
    from backend.behavior.time_fmt import format_hours_mins

    return (
        f"hard_block enabled={g.get('enabled')} locked={g.get('locked')} "
        f"productive={format_hours_mins(g.get('productive_minutes'))}/{format_hours_mins(g.get('daily_goal_minutes'))} "
        f"bible={g.get('chapter_goal_met')} morning_next={m.get('next')}"
    )


def _web_search(args: dict[str, Any]) -> str:
    query = str(args.get("query") or "").strip()
    if not query:
        return "error: query required"
    url = f"https://duckduckgo.com/?q={quote_plus(query)}"
    webbrowser.open(url)
    return f"Opened search for: {query}"


def _open_url(args: dict[str, Any]) -> str:
    raw = str(args.get("url") or "").strip()
    if not raw:
        return "error: url required"
    parsed = urlparse(raw)
    if parsed.scheme.lower() not in ("http", "https") and not raw.startswith("/"):
        return "error: only http(s) URLs or /paths allowed"
    if parsed.scheme in ("http", "https") and not parsed.netloc:
        return "error: invalid url"
    try:
        from backend.behavior.stack_health import open_calt_page

        opened = open_calt_page(raw, speak=True, auto_start=True)
        from backend.behavior.stack_health import resolve_app_url

        target = resolve_app_url(raw)
        if opened:
            return f"Opened {target}"
        return (
            f"Could not open {target} — stack start timed out or failed. "
            "Check the run.bat console, or say start_calt_stack."
        )
    except Exception as exc:  # noqa: BLE001
        webbrowser.open(raw if parsed.scheme else f"http://127.0.0.1:5173{raw}")
        return f"Opened {raw} (fallback: {exc})"


def _start_calt_stack(_args: dict[str, Any] | None = None) -> str:
    try:
        from backend.behavior.stack_health import local_jarvis_speak, start_calt_stack

        local_jarvis_speak("stack_starting", force=True)
        start_calt_stack()
        return "Launched run.bat (API + Vite). Wait ~30s then open Bible or Productivity."
    except Exception as exc:  # noqa: BLE001
        return f"error: could not start stack: {exc}"


def _resolve_app_cmd(name: str) -> list[str] | None:
    key = (name or "").strip().lower()
    if key.endswith(".exe"):
        key = key[:-4]
    candidates = _APP_ALIASES.get(key)
    if not candidates:
        return None

    # Prefer PATH / App Paths style resolution.
    for cand in candidates:
        found = shutil.which(cand)
        if found:
            return [found]

    # Common install locations for browsers / editors.
    local = os.environ.get("LOCALAPPDATA", "")
    prog = os.environ.get("ProgramFiles", r"C:\Program Files")
    prog86 = os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")
    extras: list[Path] = []
    if key in ("chrome",):
        extras += [
            Path(prog) / "Google" / "Chrome" / "Application" / "chrome.exe",
            Path(prog86) / "Google" / "Chrome" / "Application" / "chrome.exe",
            Path(local) / "Google" / "Chrome" / "Application" / "chrome.exe",
        ]
    if key in ("msedge", "edge"):
        extras += [
            Path(prog) / "Microsoft" / "Edge" / "Application" / "msedge.exe",
            Path(prog86) / "Microsoft" / "Edge" / "Application" / "msedge.exe",
        ]
    if key in ("spotify",):
        extras += [Path(local) / "Microsoft" / "WindowsApps" / "Spotify.exe"]
        extras += list(Path(local).glob("Spotify/Spotify.exe")) if local else []
    if key in ("cursor",):
        extras += [
            Path(local) / "Programs" / "cursor" / "Cursor.exe",
            Path(local) / "Programs" / "Cursor" / "Cursor.exe",
        ]
    if key in ("vscode", "code"):
        extras += [
            Path(local) / "Programs" / "Microsoft VS Code" / "Code.exe",
            Path(prog) / "Microsoft VS Code" / "Code.exe",
        ]
    for p in extras:
        if p.is_file():
            return [str(p)]

    # Built-in Windows apps usually resolve via bare name even if which fails.
    if key in ("notepad", "explorer", "calc", "calculator"):
        return [candidates[0]]
    return None


def _open_app(args: dict[str, Any]) -> str:
    name = str(args.get("name") or args.get("app") or "").strip()
    if not name:
        allowed = ", ".join(sorted(_APP_ALIASES))
        return f"error: name required (allowlist: {allowed})"
    cmd = _resolve_app_cmd(name)
    if not cmd:
        allowed = ", ".join(sorted(set(_APP_ALIASES)))
        return f"error: unknown app — not on allowlist (allowed: {allowed})"
    try:
        # shell=False; no CREATE_NO_WINDOW so GUI apps (notepad, browsers) show normally
        subprocess.Popen(cmd, shell=False)
    except OSError as exc:
        return f"error: failed to launch {name}: {exc}"
    return f"Launched {name}."


def _play_music(args: dict[str, Any]) -> str:
    uri = str(args.get("uri") or "").strip()
    query = str(args.get("query") or args.get("track") or "").strip()
    if uri:
        if uri.startswith("spotify:") or uri.startswith("https://open.spotify.com/"):
            webbrowser.open(uri)
            return f"Opened Spotify: {uri}"
        return "error: uri must be spotify: or https://open.spotify.com/..."
    if query:
        url = f"https://open.spotify.com/search/{quote_plus(query)}"
        webbrowser.open(url)
        return f"Opened Spotify search for: {query}"
    # Best-effort: try Spotify app, else Music folder
    if _resolve_app_cmd("spotify"):
        return _open_app({"name": "spotify"})
    music = Path.home() / "Music"
    if music.is_dir():
        webbrowser.open(music.as_uri())
        return f"Opened Music folder: {music}"
    return "error: no query/uri and Spotify/Music not found"


def _send_media_key(vk: int) -> str | None:
    """Send a Windows virtual-key media key via SendInput. Returns error or None."""
    if os.name != "nt":
        return "error: Windows only"
    try:
        import ctypes
        from ctypes import wintypes

        INPUT_KEYBOARD = 1
        KEYEVENTF_KEYUP = 0x0002
        MAPVK_VK_TO_VSC = 0

        user32 = ctypes.windll.user32

        class KEYBDINPUT(ctypes.Structure):
            _fields_ = [
                ("wVk", wintypes.WORD),
                ("wScan", wintypes.WORD),
                ("dwFlags", wintypes.DWORD),
                ("time", wintypes.DWORD),
                ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong)),
            ]

        class INPUT(ctypes.Structure):
            class _I(ctypes.Union):
                _fields_ = [("ki", KEYBDINPUT)]

            _anonymous_ = ("i",)
            _fields_ = [("type", wintypes.DWORD), ("i", _I)]

        scan = user32.MapVirtualKeyW(vk, MAPVK_VK_TO_VSC)

        def _one(flags: int) -> INPUT:
            inp = INPUT()
            inp.type = INPUT_KEYBOARD
            inp.ki = KEYBDINPUT(vk, scan, flags, 0, None)
            return inp

        down = _one(0)
        up = _one(KEYEVENTF_KEYUP)
        n = user32.SendInput(2, (INPUT * 2)(down, up), ctypes.sizeof(INPUT))
        if n != 2:
            return "error: SendInput failed"
        return None
    except Exception as exc:  # noqa: BLE001
        return f"error: media key failed: {exc}"


# VK_MEDIA_* / volume
_VK_MEDIA_PLAY_PAUSE = 0xB3
_VK_VOLUME_MUTE = 0xAD
_VK_VOLUME_DOWN = 0xAE
_VK_VOLUME_UP = 0xAF


def _media_play() -> str:
    err = _send_media_key(_VK_MEDIA_PLAY_PAUSE)
    return err or "Play/Pause sent."


def _volume_up() -> str:
    err = _send_media_key(_VK_VOLUME_UP)
    return err or "Volume up."


def _volume_down() -> str:
    err = _send_media_key(_VK_VOLUME_DOWN)
    return err or "Volume down."


def _volume_mute() -> str:
    err = _send_media_key(_VK_VOLUME_MUTE)
    return err or "Mute toggled."


def _set_volume(args: dict[str, Any]) -> str:
    try:
        level = int(args.get("level") if args.get("level") is not None else args.get("percent"))
    except (TypeError, ValueError):
        return "error: level required (0–100)"
    level = max(0, min(100, level))

    # Optional pycaw (not a hard dep)
    try:
        from ctypes import POINTER, cast

        from comtypes import CLSCTX_ALL  # type: ignore[import-untyped]
        from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume  # type: ignore[import-untyped]

        devices = AudioUtilities.GetSpeakers()
        interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
        volume = cast(interface, POINTER(IAudioEndpointVolume))
        volume.SetMasterVolumeLevelScalar(level / 100.0, None)
        return f"Volume set to {level}% (pycaw)."
    except Exception:  # noqa: BLE001
        pass

    # nircmd if on PATH
    nircmd = shutil.which("nircmd") or shutil.which("nircmd.exe")
    if nircmd:
        # nircmd setspeaker 0–65535
        raw = int(round(level / 100.0 * 65535))
        try:
            subprocess.run(
                [nircmd, "setsysvolume", str(raw)],
                check=False,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0,
            )
            return f"Volume set to {level}% (nircmd)."
        except OSError as exc:
            return f"error: nircmd failed: {exc}"

    return (
        f"error: cannot set exact volume to {level}% "
        "(install pycaw or nircmd; use volume_up/volume_down/volume_mute instead)"
    )


def _battery_line() -> str:
    if os.name != "nt":
        return "battery=n/a"
    try:
        import ctypes
        from ctypes import wintypes

        class SYSTEM_POWER_STATUS(ctypes.Structure):
            _fields_ = [
                ("ACLineStatus", wintypes.BYTE),
                ("BatteryFlag", wintypes.BYTE),
                ("BatteryLifePercent", wintypes.BYTE),
                ("SystemStatusFlag", wintypes.BYTE),
                ("BatteryLifeTime", wintypes.DWORD),
                ("BatteryFullLifeTime", wintypes.DWORD),
            ]

        status = SYSTEM_POWER_STATUS()
        if not ctypes.windll.kernel32.GetSystemPowerStatus(ctypes.byref(status)):
            return "battery=unknown"
        pct = status.BatteryLifePercent
        if pct == 255:
            return "battery=unknown"
        ac = "AC" if status.ACLineStatus == 1 else "battery"
        return f"battery={pct}% ({ac})"
    except Exception:  # noqa: BLE001
        return "battery=unknown"


def _system_info(user_id: int) -> str:
    now = datetime.now(_local_tz())
    parts = [
        f"time={now.strftime('%H:%M:%S')}",
        f"date={now.strftime('%Y-%m-%d %A')}",
        _battery_line(),
    ]
    try:
        parts.append(_gate_status(user_id))
    except Exception as exc:  # noqa: BLE001
        parts.append(f"gate=error:{exc}")
    return " | ".join(parts)


def _pc_lock() -> str:
    if os.name != "nt":
        return "error: Windows only"
    subprocess.run(
        ["rundll32.exe", "user32.dll,LockWorkStation"],
        check=False,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    return "Workstation lock requested."


def _pc_shutdown() -> str:
    if os.name != "nt":
        return "error: Windows only"
    subprocess.run(
        ["shutdown", "/s", "/t", "30", "/c", "CALT Voice Agent: shutting down in 30s"],
        check=False,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    return "Shutdown scheduled in 30 seconds. Say cancel shutdown if you need to abort via Start menu."


def _pc_sleep() -> str:
    if os.name != "nt":
        return "error: Windows only"
    # Hibernate/sleep via powercfg / SetSuspendState
    subprocess.run(
        ["rundll32.exe", "powrprof.dll,SetSuspendState", "0", "1", "0"],
        check=False,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    return "Sleep requested."


def _set_hard_block(user_id: int, enabled: bool) -> str:
    from backend.behavior.productivity_policy import update_policy
    from backend.db.session import SessionLocal

    db = SessionLocal()
    try:
        update_policy(db, user_id, {"hard_block_enabled": enabled})
    finally:
        db.close()
    return f"Hard-block {'armed' if enabled else 'disarmed'}."


def execute_tool(user_id: int, name: str, args: dict[str, Any] | None = None) -> str:
    args = args or {}
    name = (name or "").strip()
    known = {t["name"] for t in TOOL_SPECS}
    if name not in known:
        return f"error: unknown tool {name}"
    if name == "calendar_today":
        return _calendar_today(user_id)
    if name == "calendar_add":
        return _calendar_add(user_id, args)
    if name == "memory_get":
        return mem.memory_get(user_id, args.get("key"))
    if name == "memory_set":
        return mem.memory_set(user_id, str(args.get("key") or ""), str(args.get("value") or ""))
    if name == "gate_status":
        return _gate_status(user_id)
    if name == "web_search":
        return _web_search(args)
    if name == "open_url":
        return _open_url(args)
    if name == "start_calt_stack":
        return _start_calt_stack(args)
    if name == "open_app":
        return _open_app(args)
    if name == "play_music":
        return _play_music(args)
    if name == "media_play":
        return _media_play()
    if name == "volume_up":
        return _volume_up()
    if name == "volume_down":
        return _volume_down()
    if name == "volume_mute":
        return _volume_mute()
    if name == "set_volume":
        return _set_volume(args)
    if name == "system_info":
        return _system_info(user_id)
    if name == "pc_lock":
        return _pc_lock()
    if name == "pc_shutdown":
        return _pc_shutdown()
    if name == "pc_sleep":
        return _pc_sleep()
    if name == "hard_block_arm":
        return _set_hard_block(user_id, True)
    if name == "hard_block_disarm":
        return _set_hard_block(user_id, False)
    return f"error: unhandled {name}"


def confirm_prompt(name: str) -> str:
    prompts = {
        "pc_lock": "Lock the workstation now?",
        "pc_shutdown": "Shut down the PC in 30 seconds?",
        "pc_sleep": "Put the PC to sleep now?",
        "hard_block_arm": "Arm game hard-block?",
        "hard_block_disarm": "Disarm game hard-block?",
    }
    return prompts.get(name, f"Confirm {name}?")
