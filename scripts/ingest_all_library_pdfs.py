"""Ingest all PDF textbooks in raw_library (MML ch 1-2 + full books)."""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.corpus.ingest import ingest_path
from backend.corpus.library import FULL_BOOK_SUBJECTS, ingest_all_full_books
from backend.corpus.paths import RAW_LIBRARY_DIR
from backend.corpus.registry import chunk_count

MML_CHAPTERS = [1, 2]


def main() -> int:
    results: list[dict] = []

    mml_folder = RAW_LIBRARY_DIR / "linear_algebra"
    for ch in MML_CHAPTERS:
        t0 = time.time()
        print(f"Ingesting MML chapter {ch}...", flush=True)
        r = ingest_path(source="textbook", path=mml_folder, chapter=ch)
        results.append({"subject": "linear_algebra", "chapter": ch, **r, "seconds": round(time.time() - t0, 1)})
        print(f"  -> {r.get('chunks_ingested', 0)} chunks ({time.time() - t0:.0f}s)", flush=True)

    t0 = time.time()
    print("Ingesting full books on disk...", flush=True)
    full = ingest_all_full_books(skip_indexed=False, log=lambda line: print(line, flush=True))
    results.append({"full_books": full, "seconds": round(time.time() - t0, 1)})

    print("\n=== Summary ===", flush=True)
    print(f"Total registry chunks: {chunk_count()}", flush=True)
    print(f"Full-book subjects: {', '.join(FULL_BOOK_SUBJECTS)}", flush=True)
    print(json.dumps(results, indent=2), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
