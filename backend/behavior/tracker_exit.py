"""Exit confirmation for desktop tracker (self-control, not malware-grade).

Stop/restart/uninstall bats and tray free-time PIN check only when
``TRACKER_EXIT_PIN`` is set in the environment. With no PIN, those actions
proceed without typing a phrase.
"""

from __future__ import annotations

import os
import secrets
import sys


def exit_confirmation_required() -> bool:
    """True when TRACKER_EXIT_PIN is configured."""
    return bool((os.environ.get("TRACKER_EXIT_PIN") or "").strip())


def expected_exit_secret() -> str:
    """PIN the user must type when exit confirmation is required."""
    return (os.environ.get("TRACKER_EXIT_PIN") or "").strip()


def normalize_exit_input(value: str | None) -> str:
    return " ".join((value or "").strip().split())


def exit_secret_accepted(typed: str | None) -> bool:
    """Compare typed confirm vs TRACKER_EXIT_PIN (case-insensitive)."""
    if not exit_confirmation_required():
        return True
    want = normalize_exit_input(expected_exit_secret()).casefold()
    got = normalize_exit_input(typed).casefold()
    if not want or not got:
        return False
    # Pad to equal length so compare_digest never raises on mismatch size.
    n = max(len(want), len(got))
    return secrets.compare_digest(got.ljust(n), want.ljust(n)) and len(got) == len(want)


def exit_prompt_hint() -> str:
    """Short hint for the confirm dialog (never reveals the full env PIN)."""
    if exit_confirmation_required():
        return "Type your TRACKER_EXIT_PIN to continue."
    return "Confirm to continue."


def prompt_exit_secret_cli(*, reason: str = "stop tracker") -> bool:
    """Interactive console prompt for bats. Returns True if allowed."""
    if not exit_confirmation_required():
        return True
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
    print("Denied — wrong PIN.")
    return False


def main_cli() -> int:
    """``python -m backend.behavior.tracker_exit [--reason TEXT]`` for bats."""
    if not exit_confirmation_required():
        return 0
    reason = "stop / restart / uninstall tracker"
    argv = sys.argv[1:]
    if argv and argv[0] in ("--reason", "-r") and len(argv) >= 2:
        reason = argv[1]
    elif argv and not argv[0].startswith("-"):
        reason = " ".join(argv)
    return 0 if prompt_exit_secret_cli(reason=reason) else 1


if __name__ == "__main__":
    raise SystemExit(main_cli())
