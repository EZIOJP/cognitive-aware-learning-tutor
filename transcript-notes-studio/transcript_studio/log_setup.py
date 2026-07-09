"""File logging + uncaught exception hooks for Transcript Notes Studio."""

from __future__ import annotations

import logging
import sys
import threading
import traceback
from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler
from pathlib import Path

from transcript_studio.paths import repo_root

_LOG: logging.Logger | None = None
_LOG_PATH: Path | None = None


def log_file_path() -> Path:
    global _LOG_PATH
    if _LOG_PATH is not None:
        return _LOG_PATH
    path = repo_root() / "data" / "logs" / "transcript_studio.log"
    path.parent.mkdir(parents=True, exist_ok=True)
    _LOG_PATH = path
    return path


def setup_logging(*, level: int = logging.INFO) -> logging.Logger:
    """Configure rotating file log + console. Safe to call once at app start."""
    global _LOG
    if _LOG is not None:
        return _LOG

    log_path = log_file_path()
    root = logging.getLogger()
    root.setLevel(level)

    fmt = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    file_handler = RotatingFileHandler(
        log_path,
        maxBytes=2_000_000,
        backupCount=3,
        encoding="utf-8",
    )
    file_handler.setFormatter(fmt)
    root.addHandler(file_handler)

    console = logging.StreamHandler(sys.stderr)
    console.setLevel(logging.WARNING)
    console.setFormatter(fmt)
    # Windows console defaults to cp1252 — unicode progress arrows must not crash logging.
    if hasattr(sys.stderr, "reconfigure"):
        try:
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
        except (OSError, ValueError):
            pass
    root.addHandler(console)

    _LOG = logging.getLogger("transcript_studio")
    _LOG.info("=== Transcript Notes Studio session %s ===", datetime.now(timezone.utc).isoformat())
    _LOG.info("Log file: %s", log_path)
    _LOG.info("Shared log dir: %s", log_path.parent)
    for name in ("backend.log", "notes_generation.log", "corpus_setup_latest.log"):
        sibling = log_path.parent / name
        _LOG.info("  %s %s", name, "exists" if sibling.is_file() else "(not created yet)")

    _install_exception_hooks()
    return _LOG


def _install_exception_hooks() -> None:
    def main_hook(exc_type, exc, tb) -> None:
        logging.getLogger("transcript_studio.crash").critical(
            "Uncaught exception",
            exc_info=(exc_type, exc, tb),
        )
        _try_show_crash_dialog(exc)

    sys.excepthook = main_hook

    if hasattr(threading, "excepthook"):
        def thread_hook(args: threading.ExceptHookArgs) -> None:
            logging.getLogger("transcript_studio.crash").critical(
                "Uncaught exception in thread %s",
                args.thread.name if args.thread else "?",
                exc_info=(args.exc_type, args.exc_value, args.exc_traceback),
            )
            _try_show_crash_dialog(args.exc_value)

        threading.excepthook = thread_hook  # type: ignore[attr-defined]


def _try_show_crash_dialog(exc: BaseException) -> None:
    """Best-effort modal if Tk is running — never raise."""
    try:
        import tkinter as tk

        root = tk._default_root  # noqa: SLF001
        if root is None:
            return
        from transcript_studio.error_dialog import format_exception, show_detailed_error

        details = format_exception(exc)
        root.after(
            0,
            lambda: show_detailed_error(
                root,
                title="Transcript Notes Studio crashed",
                summary=f"{type(exc).__name__}: {exc}",
                details=details,
                log_path=str(log_file_path()),
            ),
        )
    except Exception:
        pass


def log_error(context: str, exc: BaseException) -> None:
    """Record an error with full traceback for later diagnosis."""
    logging.getLogger("transcript_studio").error(
        "%s: %s\n%s",
        context,
        exc,
        "".join(traceback.format_exception(type(exc), exc, exc.__traceback__)),
    )


def tail_log(max_lines: int = 40) -> str:
    """Return last lines of the log file for in-app display."""
    path = log_file_path()
    if not path.is_file():
        return "(no log file yet)"
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        return "\n".join(lines[-max_lines:])
    except OSError as exc:
        return f"(could not read log: {exc})"
