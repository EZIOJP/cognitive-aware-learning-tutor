"""Windows single-instance mutex for desktop tracker."""

from __future__ import annotations

import ctypes
import logging
import sys
from ctypes import wintypes

log = logging.getLogger("desktop_tracker")

MUTEX_NAME = r"Global\CognitiveAwareTutor.DesktopTracker"
ERROR_ALREADY_EXISTS = 183

_mutex_handle: int | None = None


def acquire_single_instance() -> bool:
    """Return True if this process owns the tracker mutex."""
    global _mutex_handle
    if sys.platform != "win32":
        return True

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    CreateMutexW = kernel32.CreateMutexW
    CreateMutexW.argtypes = [wintypes.LPVOID, wintypes.BOOL, wintypes.LPCWSTR]
    CreateMutexW.restype = wintypes.HANDLE

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
