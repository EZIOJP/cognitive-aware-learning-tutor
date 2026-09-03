"""Atomic text writes via temp file + os.replace."""

from __future__ import annotations

import os
from pathlib import Path


def atomic_write_text(path: Path | str, text: str, *, encoding: str = "utf-8") -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_suffix(target.suffix + ".tmp")
    tmp.write_text(text, encoding=encoding)
    os.replace(tmp, target)
