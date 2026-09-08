"""Drive ESP32 system LED over USB serial — on / off / blink patterns."""

from __future__ import annotations

import os
import threading
from typing import Any

_lock = threading.Lock()

# Single-char protocol (see hardware/eeg/src/main.cpp handleSerial)
_ACTIONS: dict[str, str] = {
    "off": "0",
    "on": "1",
    "slow": "2",
    "fast": "3",
    "double": "4",
    "heartbeat": "5",
}


def list_candidate_ports() -> list[str]:
    try:
        from serial.tools import list_ports
    except ImportError:
        return []
    out: list[str] = []
    for p in list_ports.comports():
        vid = getattr(p, "vid", None)
        if vid in (0x303A, 0x10C4, 0x1A86, 0x0403):
            out.append(p.device)
        elif p.description and "USB" in p.description.upper():
            out.append(p.device)
    return out


def resolve_port(explicit: str | None = None) -> str | None:
    if explicit:
        return explicit
    env = os.environ.get("EEG_SERIAL_PORT", "").strip()
    if env:
        return env
    ports = list_candidate_ports()
    return ports[0] if ports else None


def send_led(action: str, *, port: str | None = None) -> dict[str, Any]:
    """Soft-fail LED command over USB. Never raises to the API layer."""
    key = (action or "").strip().lower()
    ch = _ACTIONS.get(key)
    if not ch:
        return {
            "ok": False,
            "error": f"unknown action {action!r}",
            "actions": sorted(_ACTIONS.keys()),
        }

    try:
        import serial
    except ImportError:
        return {"ok": False, "error": "pyserial not installed (pip install pyserial)"}

    resolved = resolve_port(port)
    if not resolved:
        return {
            "ok": False,
            "error": "no ESP32 serial port found — plug USB and check Device Manager",
            "ports": list_candidate_ports(),
        }

    with _lock:
        try:
            ser = serial.Serial(resolved, 115200, timeout=0.5, write_timeout=1.0)
            try:
                ser.write(ch.encode("ascii"))
                ser.flush()
            finally:
                ser.close()
        except Exception as exc:
            return {
                "ok": False,
                "error": str(exc),
                "port": resolved,
            }

    return {"ok": True, "action": key, "port": resolved, "sent": ch}


def serial_status() -> dict[str, Any]:
    ports = list_candidate_ports()
    resolved = resolve_port()
    return {
        "serial_port": resolved,
        "serial_ports": ports,
        "serial_ready": bool(resolved),
        "led_actions": sorted(_ACTIONS.keys()),
    }
