"""Foreground window capture on Windows."""

from __future__ import annotations

import ctypes
import ctypes.wintypes
import sys

try:
    import psutil
except ImportError:
    psutil = None  # type: ignore[assignment]


def get_foreground_info() -> tuple[str, str, int]:
    """Return (exe_name, window_title, pid). All empty on failure."""
    if sys.platform != "win32" or psutil is None:
        return "", "", 0

    user32 = ctypes.windll.user32
    hwnd = user32.GetForegroundWindow()
    if not hwnd:
        return "", "", 0
    n = user32.GetWindowTextLengthW(hwnd) + 1
    buf = ctypes.create_unicode_buffer(n)
    user32.GetWindowTextW(hwnd, buf, n)
    title = buf.value.strip()
    pid = ctypes.wintypes.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    try:
        exe = psutil.Process(pid.value).name()
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        exe = "unknown.exe"
    return exe, title, pid.value
