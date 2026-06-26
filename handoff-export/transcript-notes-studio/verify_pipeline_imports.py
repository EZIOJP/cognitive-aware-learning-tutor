"""Verify Transcript Notes Studio can import the backend notes pipeline."""

from __future__ import annotations

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

_STUDIO_ROOT = Path(__file__).resolve().parent
if str(_STUDIO_ROOT) not in sys.path:
    sys.path.insert(0, str(_STUDIO_ROOT))

MODULES = [
    "httpx",
    "pydantic",
    "numpy",
    "backend.transcripts.notes_generator",
    "backend.transcripts.path_utils",
    "transcript_studio.notes_generator",
]


def main() -> int:
    failed: list[str] = []
    for name in MODULES:
        try:
            __import__(name)
            print(f"  OK  {name}")
        except ImportError as exc:
            print(f"  FAIL {name}: {exc}")
            failed.append(name)
    if failed:
        print(f"\nMissing {len(failed)} module(s). Run: pip install -r requirements.txt")
        return 1
    print("\nAll pipeline imports OK.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
