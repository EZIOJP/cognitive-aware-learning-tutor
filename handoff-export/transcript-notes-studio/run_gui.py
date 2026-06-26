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

# Avoid tokenizer subprocess warnings on Windows during embedding
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

from transcript_studio.log_setup import setup_logging

setup_logging()

from transcript_studio.gui import main

if __name__ == "__main__":
    main()
