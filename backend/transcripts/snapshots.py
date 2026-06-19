"""Append snapshot markers and serve slide images for lecture transcripts."""

from __future__ import annotations

import re
from pathlib import Path

from backend.paths import SNAPSHOTS_DIR

SNAPSHOT_MARKER_RE = re.compile(r"^\[SNAPSHOT\s+(\d+)\]\s*$", re.MULTILINE)


def snapshot_dir_for_transcript(transcript_filename: str) -> Path:
    stem = Path(transcript_filename).stem
    return SNAPSHOTS_DIR / stem


def next_snapshot_index(transcript_path: Path) -> int:
    if not transcript_path.is_file():
        return 1
    text = transcript_path.read_text(encoding="utf-8")
    nums = [int(m.group(1)) for m in SNAPSHOT_MARKER_RE.finditer(text)]
    return max(nums, default=0) + 1


def append_snapshot_marker(transcript_path: Path, index: int) -> str:
    marker = f"[SNAPSHOT {index}]"
    with transcript_path.open("a", encoding="utf-8") as f:
        f.write(f"\n{marker}\n")
    return marker


def save_snapshot_png(transcript_filename: str, index: int, data: bytes) -> Path:
    dest_dir = snapshot_dir_for_transcript(transcript_filename)
    dest_dir.mkdir(parents=True, exist_ok=True)
    path = dest_dir / f"{index}.png"
    path.write_bytes(data)
    return path


def resolve_snapshot_path(transcript_stem: str, index: int) -> Path:
    path = (SNAPSHOTS_DIR / transcript_stem / f"{index}.png").resolve()
    if not path.is_relative_to(SNAPSHOTS_DIR.resolve()):
        raise ValueError("Invalid snapshot path.")
    return path


def inject_snapshot_images(raw: str, transcript_stem: str) -> str:
    """Replace [SNAPSHOT N] lines with markdown image refs before Ollama summarization."""

    def repl(match: re.Match[str]) -> str:
        n = int(match.group(1))
        api = f"/api/transcripts/snapshots/{transcript_stem}/{n}.png"
        return f"\n![Slide {n}]({api})\n"

    return SNAPSHOT_MARKER_RE.sub(repl, raw)
