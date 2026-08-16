"""Windows single-instance mutex for desktop tracker."""

from __future__ import annotations

import ctypes
import logging
import sys
from ctypes import wintypes

log = logging.getLogger("desktop_tracker")

# One name only — Local\ is enough for a per-user commitment tracker.
MUTEX_NAME = r"Local\CognitiveAwareTutor.DesktopTracker"
# Older builds used Global\; treat that as "already running" too.
LEGACY_MUTEX_NAMES: tuple[str, ...] = (r"Global\CognitiveAwareTutor.DesktopTracker",)

ERROR_ALREADY_EXISTS = 183
SYNCHRONIZE = 0x00100000

_mutex_handle: int | None = None


def _open_existing(kernel32: ctypes.WinDLL, name: str) -> int:
    OpenMutexW = kernel32.OpenMutexW
    OpenMutexW.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.LPCWSTR]
    OpenMutexW.restype = wintypes.HANDLE
    return int(OpenMutexW(SYNCHRONIZE, False, name) or 0)


def acquire_single_instance() -> bool:
    """Return True if this process owns the tracker mutex (no duplicate instances)."""
    global _mutex_handle
    if sys.platform != "win32":
        return True

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

    for name in (MUTEX_NAME, *LEGACY_MUTEX_NAMES):
        existing = _open_existing(kernel32, name)
        if existing:
            kernel32.CloseHandle(existing)
            log.info("Another desktop tracker instance is already running — exiting.")
            return False

    CreateMutexW = kernel32.CreateMutexW
    CreateMutexW.argtypes = [wintypes.LPVOID, wintypes.BOOL, wintypes.LPCWSTR]
    CreateMutexW.restype = wintypes.HANDLE

    ctypes.set_last_error(0)
    handle = CreateMutexW(None, True, MUTEX_NAME)
    if handle == 0:
        log.error("CreateMutexW failed")
        return False
    if ctypes.get_last_error() == ERROR_ALREADY_EXISTS:
        kernel32.CloseHandle(handle)
        log.info("Another desktop tracker instance is already running — exiting.")
        return False
    _mutex_handle = handle
    return True


def release_single_instance() -> None:
    global _mutex_handle
    if _mutex_handle and sys.platform == "win32":
        ctypes.WinDLL("kernel32").CloseHandle(_mutex_handle)
        _mutex_handle = None
