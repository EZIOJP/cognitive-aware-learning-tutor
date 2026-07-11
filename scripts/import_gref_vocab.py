#!/usr/bin/env python3
"""Import GRE word lists from gref_material/gre words/ into the vocab bank."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main() -> int:
    parser = argparse.ArgumentParser(description="Import GRE vocab from gref_material")
    parser.add_argument("--replace", action="store_true", help="Replace entire word bank")
    parser.add_argument("--dry-run", action="store_true", help="Parse only; do not write DB")
    parser.add_argument("--no-reset-progress", action="store_true")
    parser.add_argument("--no-clear-review", action="store_true")
    args = parser.parse_args()

    from backend.db.base import SessionLocal
    from backend.paths import GREF_MATERIAL_DIR
    from backend.quiz import review_cards as rc_mod
    from backend.vocab.gref_import import (
        collect_gref_entries,
        dry_run_stats,
        has_usable_meaning,
        merge_into_bank,
    )
    from backend.vocab.normalize import GROUP_SIZE
    from backend.vocab.repository import load_words, save_words
    from backend.models import WordProgress

    print("Folder:", GREF_MATERIAL_DIR)
    stats = dry_run_stats()
    print(
        f"Parsed unique={stats['unique_words']} with_meaning={stats['with_meaning']} stubs={stats['stubs']}"
    )
    if args.dry_run:
        return 0

    imported = collect_gref_entries()
    db = SessionLocal()
    try:
        existing = [] if args.replace else load_words(db)
        merged, merge_stats = merge_into_bank(existing, imported, replace=args.replace)
        for i, w in enumerate(merged):
            w["group_number"] = (i // GROUP_SIZE) + 1
            w.setdefault("examples", [])
            w.setdefault("synonyms", [])
            w.setdefault("antonyms", [])
            w.setdefault("tags", [])
        save_words(db, merged)
        print("Saved:", merge_stats, "with_meaning=", sum(1 for w in merged if has_usable_meaning(w)))

        if not args.no_reset_progress:
            n = db.query(WordProgress).delete()
            db.commit()
            print("WordProgress deleted:", n)

        if not args.no_clear_review:
            n = rc_mod.clear_review_cards(db, user_id=None)
            print("ReviewCards deleted:", n)
    finally:
        db.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
