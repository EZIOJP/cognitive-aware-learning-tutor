#!/usr/bin/env python3
"""Launch Classic Notes GUI (LM Studio only)."""

from __future__ import annotations

import os
import sys
from pathlib import Path

_STUDIO = Path(__file__).resolve().parent
_REPO_ROOT = _STUDIO.parent
for p in (_REPO_ROOT, _STUDIO):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))


def _load_repo_dotenv() -> None:
    env_path = _REPO_ROOT / ".env"
    if not env_path.is_file():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


_load_repo_dotenv()
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

from transcript_studio.legacy_notes_gui import main  # noqa: E402

if __name__ == "__main__":
    main()
