"""Idle-time detection via Win32 GetLastInputInfo."""

from __future__ import annotations

import ctypes
import sys
from ctypes import wintypes


class LASTINPUTINFO(ctypes.Structure):
    _fields_ = [("cbSize", ctypes.c_uint), ("dwTime", ctypes.c_uint)]


def get_idle_seconds() -> float:
    """Seconds since last keyboard/mouse input. Returns 0 on non-Windows or failure."""
    if sys.platform != "win32":
        return 0.0

    user32 = ctypes.WinDLL("user32", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

    lii = LASTINPUTINFO()
    lii.cbSize = ctypes.sizeof(LASTINPUTINFO)
    if not user32.GetLastInputInfo(ctypes.byref(lii)):
        return 0.0

    tick = kernel32.GetTickCount()
    idle_ms = tick - lii.dwTime
    return max(0.0, idle_ms / 1000.0)
