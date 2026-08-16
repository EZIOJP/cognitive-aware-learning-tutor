"""Exit confirmation for desktop tracker (self-control, not malware-grade).

Tray Exit and stop/restart/uninstall bats require typed phrase or PIN from env
``TRACKER_EXIT_PIN``. Default phrase: ``I AM DONE TRACKING`` (case-insensitive).
"""

from __future__ import annotations

import os
import secrets
import sys


DEFAULT_EXIT_PHRASE = "I AM DONE TRACKING"


def expected_exit_secret() -> str:
    """PIN or phrase the user must type to quit the tracker."""
    raw = (os.environ.get("TRACKER_EXIT_PIN") or "").strip()
    return raw if raw else DEFAULT_EXIT_PHRASE


def normalize_exit_input(value: str | None) -> str:
    return " ".join((value or "").strip().split())


def exit_secret_accepted(typed: str | None) -> bool:
    """Compare typed confirm vs expected secret (case-insensitive)."""
    want = normalize_exit_input(expected_exit_secret()).casefold()
    got = normalize_exit_input(typed).casefold()
    if not want or not got:
        return False
    # Pad to equal length so compare_digest never raises on mismatch size.
    n = max(len(want), len(got))
    return secrets.compare_digest(got.ljust(n), want.ljust(n)) and len(got) == len(want)


def exit_prompt_hint() -> str:
    """Short hint for the confirm dialog (never reveals the full env PIN)."""
    if (os.environ.get("TRACKER_EXIT_PIN") or "").strip():
        return "Type your TRACKER_EXIT_PIN to quit."
    return f'Type "{DEFAULT_EXIT_PHRASE}" to quit.'


def prompt_exit_secret_cli(*, reason: str = "stop tracker") -> bool:
    """Interactive console prompt for bats. Returns True if secret accepted."""
    print(f"CALT tracker — confirm required to {reason}.")
    print(exit_prompt_hint())
    try:
        typed = input("> ")
    except (EOFError, KeyboardInterrupt):
        print("Cancelled.")
        return False
    if exit_secret_accepted(typed):
        print("OK.")
        return True
    print("Denied — wrong PIN/phrase.")
    return False


def main_cli() -> int:
    """``python -m backend.behavior.tracker_exit [--reason TEXT]`` for bats."""
    reason = "stop / restart / uninstall tracker"
    argv = sys.argv[1:]
    if argv and argv[0] in ("--reason", "-r") and len(argv) >= 2:
        reason = argv[1]
    elif argv and not argv[0].startswith("-"):
        reason = " ".join(argv)
    return 0 if prompt_exit_secret_cli(reason=reason) else 1


if __name__ == "__main__":
    raise SystemExit(main_cli())
