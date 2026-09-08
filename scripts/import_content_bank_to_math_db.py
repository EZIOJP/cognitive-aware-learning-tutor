"""Import curated data/questions/math/** into SQLite math_questions.

Does NOT delete JSON packs.

Usage:
  python scripts/import_content_bank_to_math_db.py
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.db.session import SessionLocal
from backend.quiz import content_bank as cb


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--kind", default="math")
    args = parser.parse_args()
    db = SessionLocal()
    try:
        result = cb.sync_curated_to_db(db, kind=args.kind)
        print(result)
    finally:
        db.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
