"""Deprecated: do not use as the Focus launcher.

Owner 2026-09-07: control UI is native/calt_focus (C++ tray + WebView2).
This Python/pystray module is kept only so old imports do not crash; it prints
a redirect and exits.
"""

from __future__ import annotations

import sys


def run() -> int:
    print(
        "[focus_desktop] Deprecated.\n"
        "Use: scripts\\desktop_tracker\\run_calt_desktop.bat\n"
        "     → native calt_focus.exe (C++ tray + WebView2)\n"
        "Build: scripts\\desktop_tracker\\build_native_focus.bat",
        file=sys.stderr,
    )
    return 2
