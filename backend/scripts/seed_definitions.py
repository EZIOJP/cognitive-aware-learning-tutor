"""Seed reading definitions and default user plugins."""

from backend.db.base import SessionLocal
from backend.hub.services.seed import seed_reading_definitions, seed_user_plugins
from backend.models import User


def main() -> None:
    db = SessionLocal()
    try:
        seed_reading_definitions(db)
        for username in ("admin", "demo"):
            user = db.query(User).filter(User.username == username).first()
            if user:
                seed_user_plugins(db, user.id)
        print("Seeded reading_definitions and user_plugins.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
