"""CLI: log_tracker_launch.py <mode> <message...>"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from backend.behavior.tracker_storage import append_launcher_log  # noqa: E402

if __name__ == "__main__":
    if len(sys.argv) >= 3:
        append_launcher_log(sys.argv[1], " ".join(sys.argv[2:]))
