"""One-shot: hard reclassify today's TrackedSession categories (local day).

Usage (from repo root):
  python scripts/reclassify_today.py
  python scripts/reclassify_today.py --user-id 1
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.behavior.reclassify_today import reclassify_today  # noqa: E402
from backend.db.base import SessionLocal  # noqa: E402
from backend.timetable.tracker_query import primary_tracker_user_id  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Hard reclassify today's tracked sessions")
    parser.add_argument("--user-id", type=int, default=None, help="User id (default: primary tracker / admin)")
    parser.add_argument("--dry-run", action="store_true", help="Flush only — do not commit")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        uid = args.user_id or primary_tracker_user_id(db)
        result = reclassify_today(db, uid, commit=not args.dry_run)
        print(json.dumps(result, indent=2, ensure_ascii=False))
        print(
            f"\nUpdated {result['updated']}/{result['scanned']} rows. "
            f"Productive minutes: {result['productive_minutes_before']} -> {result['productive_minutes_after']}"
        )
        sleep = result.get("sleep_overwrite") or {}
        if sleep.get("stamped"):
            print(f"Sleep overwrite stamped {sleep['stamped']} PC sessions as non-productive.")
        if args.dry_run:
            db.rollback()
            print("(dry-run: rolled back)")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
