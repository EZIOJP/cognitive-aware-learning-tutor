"""Cached system status — avoids blocking UI on every tab refresh."""

from __future__ import annotations

import time
import urllib.error
import urllib.request
from typing import Any

from backend.behavior.calt_desktop.constants import HUB_HEALTH_URL

_CACHE: dict[str, Any] | None = None
_CACHE_AT: float = 0.0
_CACHE_TTL_S = 6.0
_CACHE_TTL_WEB_DOWN_S = 30.0


def _cache_ttl_s(status: dict[str, Any] | None) -> float:
    """Backoff status polls when web is down (avoids hammering hung Vite)."""
    if status is not None and not status.get("web_up"):
        return _CACHE_TTL_WEB_DOWN_S
    return _CACHE_TTL_S


def probe_hub() -> bool:
    try:
        req = urllib.request.Request(HUB_HEALTH_URL, method="GET")
        with urllib.request.urlopen(req, timeout=0.8) as resp:
            return int(getattr(resp, "status", 0) or 0) == 200
    except (OSError, urllib.error.URLError, ValueError):
        return False


def collect_system_status(service: Any | None = None, *, force: bool = False) -> dict[str, Any]:
    """Return a flat status dict for UI panels (never raises)."""
    global _CACHE, _CACHE_AT
    now = time.monotonic()
    if not force and _CACHE is not None and (now - _CACHE_AT) < _cache_ttl_s(_CACHE):
        out = dict(_CACHE)
        if service is not None:
            uid = int(getattr(service, "user_id", 0) or 0)
            out["user_id"] = uid
            out["username"] = str(getattr(service, "username", "") or "")
            out["tracker_linked"] = uid > 0
            try:
                gate = service.latest_gate() or {}
                browser = gate.get("browser") or {}
                from backend.behavior.browser_gate_policy import mode_label

                out["gate_mode"] = mode_label(
                    str(browser.get("mode") or gate.get("browser_mode") or "—")
                )
                out["gate_locked"] = bool(gate.get("locked"))
                inc = gate.get("incubation") if isinstance(gate.get("incubation"), dict) else {}
                out["incubation_active"] = bool(inc.get("active") or browser.get("incubation_active"))
                desk = gate.get("desktop") if isinstance(gate.get("desktop"), dict) else {}
                try:
                    from backend.behavior.enforcer_ownership import enforcer_owns_kills
                    from backend.behavior.native_enforcer_status import collect_native_enforcer_status

                    native = collect_native_enforcer_status()
                    out.update(native)
                    out["enforcer_owns_kills"] = bool(
                        desk.get("enforcer_owns_kills") or enforcer_owns_kills()
                    )
                except Exception:  # noqa: BLE001
                    out["enforcer_owns_kills"] = bool(desk.get("enforcer_owns_kills"))
            except Exception:  # noqa: BLE001
                pass
        return out

    out: dict[str, Any] = {
        "api_up": False,
        "web_up": False,
        "hub_up": False,
        "extension_alive": False,
        "user_id": 0,
        "username": "",
        "tracker_linked": False,
        "gate_mode": "—",
        "gate_locked": False,
        "incubation_active": False,
        "enforcer_owns_kills": False,
        "native_exe_built": False,
        "native_service_running": None,
        "enforcer_lock_present": False,
        "last_kill_log": "",
        "voice_hotkey": False,
        "voice_paused_free": False,
        "voice_env_off": False,
        "desktop_ok": True,
        "stack_up": False,
    }
    try:
        from backend.behavior.stack_health import get_stack_health

        snap = get_stack_health()
        out["api_up"] = bool(snap.api_up)
        out["web_up"] = bool(snap.web_up)
        out["stack_up"] = bool(snap.api_up and snap.web_up)
    except Exception:  # noqa: BLE001
        pass

    out["hub_up"] = probe_hub()

    try:
        from backend.behavior.comms_health import extension_is_alive

        out["extension_alive"] = bool(extension_is_alive())
    except Exception:  # noqa: BLE001
        pass

    if service is not None:
        uid = int(getattr(service, "user_id", 0) or 0)
        out["user_id"] = uid
        out["username"] = str(getattr(service, "username", "") or "")
        out["tracker_linked"] = uid > 0
        try:
            gate = service.latest_gate() or {}
            browser = gate.get("browser") or {}
            from backend.behavior.browser_gate_policy import mode_label

            out["gate_mode"] = mode_label(
                str(browser.get("mode") or gate.get("browser_mode") or "—")
            )
            out["gate_locked"] = bool(gate.get("locked"))
        except Exception:  # noqa: BLE001
            pass

    try:
        from backend.behavior.native_enforcer_status import collect_native_enforcer_status

        native = collect_native_enforcer_status()
        out.update(native)
    except Exception:  # noqa: BLE001
        pass

    try:
        from backend.behavior.voice_agent import (
            is_free_mode_paused,
            is_voice_hotkey_enabled,
            voice_agent_enabled,
        )

        out["voice_env_off"] = not voice_agent_enabled()
        out["voice_paused_free"] = is_free_mode_paused()
        out["voice_hotkey"] = is_voice_hotkey_enabled()
    except Exception:  # noqa: BLE001
        pass

    _CACHE = dict(out)
    _CACHE_AT = now
    return out


def checklist_rows(status: dict[str, Any]) -> list[tuple[str, bool, str]]:
    """(label, ok, detail) for autostart / health checklist."""
    rows: list[tuple[str, bool, str]] = [
        ("CALT Desktop", bool(status.get("desktop_ok")), "tracker process"),
        ("Hub :8765", bool(status.get("hub_up")), "watch voice uploads"),
        ("API :8000", bool(status.get("api_up")), "notes · quiz · planner API"),
        ("Web :5173", bool(status.get("web_up")), "lecture notes UI"),
        ("Edge extension", bool(status.get("extension_alive")), "browser SoftLand"),
        ("Account linked", bool(status.get("tracker_linked")), status.get("username") or "log in via web"),
    ]
    native_built = bool(status.get("native_exe_built"))
    owns = bool(status.get("enforcer_owns_kills"))
    svc = status.get("native_service_running")
    if owns:
        native_detail = "owns kills+track"
    elif svc is True:
        native_detail = "service running (lock stale?)"
    elif native_built:
        native_detail = "built — install or run console"
    else:
        native_detail = "build_native_enforcer.bat"
    rows.append(("Native enforcer", owns or svc is True, native_detail))
    voice_ok = bool(status.get("voice_hotkey")) and not status.get("voice_env_off")
    if status.get("voice_env_off"):
        voice_detail = "VOICE_AGENT_ENABLED=0"
    elif status.get("voice_paused_free"):
        voice_detail = "paused in FREE mode"
        voice_ok = False
    else:
        voice_detail = "hotkey on" if status.get("voice_hotkey") else "hotkey off"
    rows.append(("Voice agent", voice_ok, voice_detail))
    return rows
