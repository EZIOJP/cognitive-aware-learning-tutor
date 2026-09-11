"""Bible PDF paths — corpus under data/productivity/bible/ (Focus owned)."""

from __future__ import annotations

import shutil
from pathlib import Path

from backend.paths import BIBLE_DATA_DIR

_SEED = Path(r"C:\Users\Lenovo\Downloads\good-news-bible.pdf")
PDF_NAME = "good-news-bible.pdf"


def bible_dir() -> Path:
    BIBLE_DATA_DIR.mkdir(parents=True, exist_ok=True)
    return BIBLE_DATA_DIR


def ensure_bible_pdf() -> Path:
    dest = bible_dir() / PDF_NAME
    if dest.is_file() and dest.stat().st_size > 0:
        return dest
    if _SEED.is_file():
        shutil.copy2(_SEED, dest)
        return dest
    raise FileNotFoundError(
        f"Bible PDF missing. Place {PDF_NAME} at {_SEED} or {dest}"
    )


def pdf_path() -> Path:
    return ensure_bible_pdf()
