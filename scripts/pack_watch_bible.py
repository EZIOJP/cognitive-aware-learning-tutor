"""Pack WEB structured Bible into per-chapter JSON for the Zepp CALT Bible app.

One file per chapter keeps every device read a few KB. Whole-book files
(up to 250 KB) exhausted watch RAM and crashed the device.
"""

from __future__ import annotations

import json
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "data" / "bible" / "structured" / "web.json"
OUT_DIRS = [
    # Device-target folder (Zeus strips screen folder → /assets/bible)
    ROOT / "packages" / "calt-bible" / "assets" / "480x480-t-rex-3" / "bible",
    # Shared raw folder (Zeus copies → /assets/raw/bible)
    ROOT / "packages" / "calt-bible" / "assets" / "raw" / "bible",
]


def _slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", (name or "").lower())


def pack(src: Path = SRC, out_dirs: list[Path] | None = None) -> dict:
    if not src.is_file():
        raise FileNotFoundError(f"WEB Bible missing at {src}")
    data = json.loads(src.read_text(encoding="utf-8"))
    books_in = data.get("books") or []
    books: list[dict] = []
    # (book_id, chapter_number, json_text)
    chapter_files: list[tuple[str, int, str]] = []
    max_chapter_bytes = 0

    for b in books_in:
        name = str(b.get("name") or "")
        book_id = str(b.get("id") or _slug(name))
        chapters_raw = b.get("chapters") or []
        num_chapters = 0

        for ch_i, verses_raw in enumerate(chapters_raw):
            verses = []
            for i, v in enumerate(verses_raw or []):
                if isinstance(v, dict):
                    text = str(v.get("text") or "").strip()
                    num = int(v.get("number") or i + 1)
                else:
                    text = str(v).strip()
                    num = i + 1
                if not text:
                    continue
                verses.append({"n": num, "t": text})
            num_chapters += 1
            payload = {"b": book_id, "name": name, "c": ch_i + 1, "v": verses}
            text_out = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
            max_chapter_bytes = max(max_chapter_bytes, len(text_out.encode("utf-8")))
            chapter_files.append((book_id, ch_i + 1, text_out))

        books.append(
            {
                "id": book_id,
                "name": name,
                "testament": str(b.get("testament") or ""),
                "n": num_chapters,
            }
        )

    # Slim index: books only. The daily plan is computed on device from `n`.
    index = {
        "version": "web",
        "versionName": str(data.get("versionName") or "World English Bible"),
        "license": str(data.get("license") or "Public Domain"),
        "books": books,
    }
    index_text = json.dumps(index, ensure_ascii=False, separators=(",", ":"))

    dirs = out_dirs or OUT_DIRS
    for out in dirs:
        if out.exists():
            shutil.rmtree(out)
        out.mkdir(parents=True, exist_ok=True)
        (out / "index.json").write_text(index_text, encoding="utf-8")
        for book_id, chapter, text_out in chapter_files:
            book_dir = out / book_id
            book_dir.mkdir(exist_ok=True)
            (book_dir / f"{chapter}.json").write_text(text_out, encoding="utf-8")

    # Stale flat-book layout from earlier versions
    legacy = ROOT / "packages" / "calt-bible" / "assets" / "bible"
    if legacy.exists():
        shutil.rmtree(legacy)

    return {
        "books": len(books),
        "chapters": len(chapter_files),
        "index_bytes": len(index_text.encode("utf-8")),
        "max_chapter_bytes": max_chapter_bytes,
        "first": f"{books[0]['id']} 1" if books else None,
        "last": f"{books[-1]['id']} {books[-1]['n']}" if books else None,
        "dirs": [str(d) for d in dirs],
    }


if __name__ == "__main__":
    try:
        info = pack()
    except Exception as e:
        print(f"pack failed: {e}", file=sys.stderr)
        sys.exit(1)
    print(
        f"packed {info['books']} books / {info['chapters']} chapters "
        f"({info['first']} -> {info['last']})"
    )
    print(
        f"index {info['index_bytes']} bytes, "
        f"largest chapter {info['max_chapter_bytes']} bytes"
    )
    for d in info["dirs"]:
        print(d)
