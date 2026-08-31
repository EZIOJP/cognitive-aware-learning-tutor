"""Entry: ``python -m backend.behavior.calt_desktop``."""

from __future__ import annotations

import multiprocessing as _mp
import sys


def main() -> None:
    from backend.behavior.calt_desktop.app import run

    raise SystemExit(run())


if __name__ == "__main__":
    if _mp.current_process().name == "MainProcess":
        main()
    else:
        sys.exit(0)
