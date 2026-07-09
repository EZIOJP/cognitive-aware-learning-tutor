#!/usr/bin/env python3
"""Launch Transcript Notes Studio GUI."""

from __future__ import annotations

import os
import sys
from pathlib import Path

# Repo root on sys.path (avoids fragile PYTHONPATH / batch \t escapes in data\transcripts)
_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))


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

# Avoid tokenizer subprocess warnings on Windows during embedding
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")
# Torch in a worker thread while Tk runs causes 0xC0000005 on Windows — use subprocess encode
os.environ.setdefault("TRANSCRIPT_STUDIO_GUI", "1")

from transcript_studio.log_setup import setup_logging

setup_logging()

from transcript_studio.gui import main

if __name__ == "__main__":
    try:
        main()
    except Exception:
        import traceback

        traceback.print_exc()
        print(f"\nLog: {_REPO_ROOT / 'data' / 'logs' / 'transcript_studio.log'}")
        input("\nPress Enter to close...")
        sys.exit(1)
