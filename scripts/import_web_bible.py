"""Rebuild data/bible/structured/web.json from javascripture WEB.json (public domain)."""

from __future__ import annotations

import json
import re
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW_URL = "https://raw.githubusercontent.com/javascripture/javascripture/gh-pages/bibles/WEB.json"
OUT = ROOT / "data" / "bible" / "structured" / "web.json"

DISPLAY = {
    "I Samuel": "1 Samuel",
    "II Samuel": "2 Samuel",
    "I Kings": "1 Kings",
    "II Kings": "2 Kings",
    "I Chronicles": "1 Chronicles",
    "II Chronicles": "2 Chronicles",
    "I Corinthians": "1 Corinthians",
    "II Corinthians": "2 Corinthians",
    "I Thessalonians": "1 Thessalonians",
    "II Thessalonians": "2 Thessalonians",
    "I Timothy": "1 Timothy",
    "II Timothy": "2 Timothy",
    "I Peter": "1 Peter",
    "II Peter": "2 Peter",
    "I John": "1 John",
    "II John": "2 John",
    "III John": "3 John",
    "Revelation of John": "Revelation",
}


def flat_verse(v) -> str:
    parts = []
    for tok in v:
        if isinstance(tok, list):
            if tok:
                parts.append(str(tok[0]))
        else:
            parts.append(str(tok))
    text = " ".join(parts)
    text = re.sub(r"\s+", " ", text).strip()
    return re.sub(r"\s+([,.;:!?])", r"\1", text)


def main() -> None:
    raw_path = ROOT / "data" / "bible" / "_web_raw.json"
    if not raw_path.is_file():
        print("Downloading WEB.json…")
        urllib.request.urlretrieve(RAW_URL, raw_path)
    raw = json.loads(raw_path.read_text(encoding="utf-8"))
    books_out = []
    in_ot = True
    for raw_name, chapters in raw["books"].items():
        name = DISPLAY.get(raw_name, raw_name)
        if raw_name == "Matthew":
            in_ot = False
        ch_list = []
        for ch in chapters:
            verses = [{"number": i + 1, "text": flat_verse(v)} for i, v in enumerate(ch)]
            ch_list.append(verses)
        books_out.append(
            {
                "id": re.sub(r"[^a-z0-9]+", "", name.lower()),
                "name": name,
                "raw_name": raw_name,
                "testament": "OT" if in_ot else "NT",
                "num_chapters": len(ch_list),
                "chapters": ch_list,
            }
        )
    out = {
        "version": "web",
        "versionName": raw.get("versionName") or "World English Bible",
        "license": "Public domain",
        "source": "javascripture WEB.json (flattened)",
        "books": books_out,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"Wrote {OUT} ({OUT.stat().st_size // 1024} KB, {len(books_out)} books)")


if __name__ == "__main__":
    main()
