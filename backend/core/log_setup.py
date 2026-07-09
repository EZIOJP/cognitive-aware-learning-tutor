"""Central file logging for the FastAPI backend — one place for all app diagnostics."""

from __future__ import annotations

import logging
import sys
import threading
import traceback
from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler
from pathlib import Path

from backend.paths import LOGS_DIR

_CONFIGURED = False
_BACKEND_LOG = LOGS_DIR / "backend.log"
_NOTES_LOG = LOGS_DIR / "notes_generation.log"


class _WindowsSafeRotatingFileHandler(RotatingFileHandler):
    """RotatingFileHandler that tolerates multi-process locks on Windows."""

    def doRollover(self) -> None:
        try:
            if self.stream:
                self.stream.close()
                self.stream = None  # type: ignore[assignment]
            super().doRollover()
        except PermissionError:
            # uvicorn reload spawns workers that share backend.log on Windows
            if self.stream is None:
                self.stream = self._open()
        except OSError:
            if self.stream is None:
                self.stream = self._open()

    def emit(self, record: logging.LogRecord) -> None:
        try:
            super().emit(record)
        except PermissionError:
            pass


def ensure_logs_dir() -> Path:
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    return LOGS_DIR


def backend_log_path() -> Path:
    ensure_logs_dir()
    return _BACKEND_LOG


def notes_log_path() -> Path:
    ensure_logs_dir()
    return _NOTES_LOG


def list_log_files() -> list[dict[str, str | int]]:
    """Return known log files under data/logs/ for the system API and UI."""
    ensure_logs_dir()
    known = {
        "backend.log": backend_log_path(),
        "notes_generation.log": notes_log_path(),
        "transcript_studio.log": LOGS_DIR / "transcript_studio.log",
        "corpus_setup_latest.log": LOGS_DIR / "corpus_setup_latest.log",
    }
    out: list[dict[str, str | int]] = []
    seen: set[Path] = set()
    for name, path in known.items():
        seen.add(path)
        out.append(_file_entry(name, path))
    for path in sorted(LOGS_DIR.glob("*.log*"), key=lambda p: p.stat().st_mtime if p.is_file() else 0, reverse=True):
        if path in seen:
            continue
        out.append(_file_entry(path.name, path))
    return out


def _file_entry(name: str, path: Path) -> dict[str, object]:
    if path.is_file():
        stat = path.stat()
        return {
            "name": name,
            "path": str(path.resolve()),
            "size_bytes": stat.st_size,
            "modified_at": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
            "exists": True,
        }
    return {
        "name": name,
        "path": str(path.resolve()),
        "size_bytes": 0,
        "modified_at": "",
        "exists": False,
    }


def tail_log_file(name: str, *, max_lines: int = 200) -> str:
    path = resolve_log_path(name)
    if not path.is_file():
        return f"(log file not found: {name})"
    try:
        return _tail_lines_from_end(path, max(1, min(max_lines, 2000)))
    except OSError as exc:
        return f"(could not read {name}: {exc})"


def _tail_lines_from_end(path: Path, max_lines: int) -> str:
    """Read only the tail of a log file — avoids loading multi-MB files on every poll."""
    chunk_size = 16_384
    with path.open("rb") as handle:
        handle.seek(0, 2)
        end = handle.tell()
        if end == 0:
            return ""
        buffer = b""
        pos = end
        line_count = 0
        while pos > 0 and line_count <= max_lines:
            read_size = min(chunk_size, pos)
            pos -= read_size
            handle.seek(pos)
            buffer = handle.read(read_size) + buffer
            line_count = buffer.count(b"\n")
        text = buffer.decode("utf-8", errors="replace")
        return "\n".join(text.splitlines()[-max_lines:])


def resolve_log_path(name: str) -> Path:
    """Only allow reading files inside data/logs/."""
    safe = Path(name).name
    if not safe or safe != name or ".." in name:
        raise ValueError("Invalid log file name")
    path = (LOGS_DIR / safe).resolve()
    if path.parent != LOGS_DIR.resolve():
        raise ValueError("Invalid log file path")
    return path


def setup_logging(*, level: int | None = None) -> logging.Logger:
    """Configure rotating backend log + stderr warnings. Safe to call once."""
    global _CONFIGURED
    import os

    if _CONFIGURED:
        return logging.getLogger("backend")

    ensure_logs_dir()
    log_level = level if level is not None else getattr(logging, os.environ.get("LOG_LEVEL", "INFO").upper(), logging.INFO)

    fmt = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    root = logging.getLogger()
    root.setLevel(log_level)

    file_handler = _WindowsSafeRotatingFileHandler(
        backend_log_path(),
        maxBytes=4_000_000,
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setFormatter(fmt)
    root.addHandler(file_handler)

    notes_handler = _WindowsSafeRotatingFileHandler(
        notes_log_path(),
        maxBytes=2_000_000,
        backupCount=3,
        encoding="utf-8",
    )
    notes_handler.setFormatter(fmt)
    notes_handler.addFilter(_NotesPipelineFilter())
    root.addHandler(notes_handler)

    if not any(isinstance(h, logging.StreamHandler) and not isinstance(h, RotatingFileHandler) for h in root.handlers):
        console = logging.StreamHandler(sys.stderr)
        console.setLevel(logging.WARNING)
        console.setFormatter(fmt)
        root.addHandler(console)

    # Benign WS disconnects during idle / uvicorn --reload spam asyncio ERROR
    logging.getLogger("asyncio").addFilter(_AsyncioWsPingFilter())

    _install_exception_hooks()

    app_log = logging.getLogger("backend")
    app_log.info("=== Backend session %s ===", datetime.now(timezone.utc).isoformat())
    app_log.info("Log dir: %s", LOGS_DIR.resolve())
    app_log.info("Main log: %s", backend_log_path())
    app_log.info("Notes log: %s", notes_log_path())

    _CONFIGURED = True
    return app_log


class _AsyncioWsPingFilter(logging.Filter):
    """Suppress benign keepalive ping timeout noise from asyncio during WS reload/idle."""

    def filter(self, record: logging.LogRecord) -> bool:
        if record.name != "asyncio":
            return True
        msg = record.getMessage()
        return "keepalive ping timeout" not in msg and "ConnectionClosedError" not in msg


class _NotesPipelineFilter(logging.Filter):
    """Duplicate notes/corpus/transcript generation lines into notes_generation.log."""

    _PREFIXES = (
        "backend.transcripts",
        "backend.corpus",
        "backend.transcripts.hybrid_notes",
        "backend.transcripts.notes_generator",
        "backend.transcripts.note_block_repair",
        "backend.transcripts.chunk_polish",
    )

    def filter(self, record: logging.LogRecord) -> bool:
        return record.name.startswith(self._PREFIXES)


def log_notes_event(message: str, *args: object) -> None:
    logging.getLogger("backend.transcripts.notes").info(message, *args)


def log_error(context: str, exc: BaseException) -> None:
    logging.getLogger("backend.error").error(
        "%s: %s\n%s",
        context,
        exc,
        "".join(traceback.format_exception(type(exc), exc, exc.__traceback__)),
    )


def _install_exception_hooks() -> None:
    def main_hook(exc_type, exc, tb) -> None:
        logging.getLogger("backend.crash").critical(
            "Uncaught exception",
            exc_info=(exc_type, exc, tb),
        )
        sys.__excepthook__(exc_type, exc, tb)

    sys.excepthook = main_hook

    if hasattr(threading, "excepthook"):
        def thread_hook(args: threading.ExceptHookArgs) -> None:
            logging.getLogger("backend.crash").critical(
                "Uncaught exception in thread %s",
                args.thread.name if args.thread else "?",
                exc_info=(args.exc_type, args.exc_value, args.exc_traceback),
            )

        threading.excepthook = thread_hook  # type: ignore[attr-defined]
