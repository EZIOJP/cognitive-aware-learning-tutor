"""Wipe quiz decks, ReviewCards, and quiz sessions (vocab words kept).

Usage:
  python scripts/wipe_practice_history.py
  python scripts/wipe_practice_history.py --user-id 1
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.db.session import SessionLocal
from backend.models import User
from backend.quiz import handler as quiz_handler


def main() -> int:
    parser = argparse.ArgumentParser(description="Wipe practice history (decks/cards/sessions)")
    parser.add_argument("--user-id", type=int, default=None, help="Limit wipe to one user id")
    parser.add_argument("--all-users", action="store_true", help="Wipe every user (default if no --user-id)")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        if args.user_id is not None:
            user = db.query(User).filter(User.id == args.user_id).first()
            if not user:
                print(f"user {args.user_id} not found")
                return 1
            result = quiz_handler.wipe_practice_history(db, user=user, all_users=False)
        else:
            result = quiz_handler.wipe_practice_history(db, user=None, all_users=True)
        print("wiped:", result)
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
