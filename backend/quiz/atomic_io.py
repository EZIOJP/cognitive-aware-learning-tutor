"""Atomic text writes via temp file + os.replace (Windows-robust)."""

from __future__ import annotations

import errno
import os
import stat
import time
from pathlib import Path

_REPLACE_ATTEMPTS = 8
_REPLACE_BACKOFF_SEC = 0.05

# Windows: 5=ACCESS_DENIED, 32=SHARING_VIOLATION. POSIX: EACCES/EAGAIN.
_RETRY_WINERRORS = frozenset({5, 32})
_RETRY_ERRNOS = frozenset({errno.EACCES, errno.EAGAIN, errno.EBUSY, errno.EPERM})


def _clear_readonly(path: Path) -> None:
    try:
        mode = path.stat().st_mode
    except OSError:
        return
    if mode & stat.S_IWRITE:
        return
    try:
        path.chmod(mode | stat.S_IWRITE)
    except OSError:
        pass


def _is_transient_replace_error(exc: OSError) -> bool:
    win = getattr(exc, "winerror", None)
    if win is not None and win in _RETRY_WINERRORS:
        return True
    if isinstance(exc, PermissionError):
        return True
    return exc.errno in _RETRY_ERRNOS


def atomic_write_text(path: Path | str, text: str, *, encoding: str = "utf-8") -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    # Same directory → same volume so os.replace is atomic on Windows.
    tmp = target.with_name(target.name + ".tmp")
    # write_text closes the handle before replace.
    tmp.write_text(text, encoding=encoding)
    last_err: BaseException | None = None
    for attempt in range(_REPLACE_ATTEMPTS):
        try:
            if target.exists():
                _clear_readonly(target)
            os.replace(tmp, target)
            return
        except OSError as exc:
            if not _is_transient_replace_error(exc):
                raise
            last_err = exc
        if attempt + 1 < _REPLACE_ATTEMPTS:
            time.sleep(_REPLACE_BACKOFF_SEC * (attempt + 1))
    try:
        tmp.unlink(missing_ok=True)
    except OSError:
        pass
    assert last_err is not None
    raise last_err
