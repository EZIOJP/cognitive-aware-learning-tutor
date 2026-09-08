"""Move all lecture subfolder notes into data_foundations/ (flat). Run once, then delete dupes in UI."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.db import SessionLocal
from backend.models import User
from backend.transcripts.library import move_note, normalize_folder_path
from backend.paths import NOTES_DIR


TARGET = "data_foundations"


def main() -> None:
    base = NOTES_DIR / TARGET
    if not base.is_dir():
        print(f"Missing folder: {base}")
        return

    md_files = sorted(
        p for p in base.rglob("*.md")
        if p.is_file() and p.parent != base and not p.name.startswith(".")
    )
    if not md_files:
        print("No subfolder notes to move.")
        return

    db = SessionLocal()
    try:
        user = db.query(User).order_by(User.id).first()
        if not user:
            print("No user in database — log in via web first.")
            return

        moved = 0
        for path in md_files:
            rel = path.relative_to(NOTES_DIR).as_posix()
            folder = normalize_folder_path(str(path.parent.relative_to(NOTES_DIR)))
            if folder == TARGET:
                continue
            dest_name = path.name
            dest_rel = f"{TARGET}/{dest_name}"
            if (NOTES_DIR / dest_rel).exists() and (NOTES_DIR / dest_rel) != path:
                stem = path.stem
                parent_tag = folder.split("/")[-1] if folder else "note"
                dest_name = f"{parent_tag}_{stem}.md"
                dest_rel = f"{TARGET}/{dest_name}"

            try:
                move_note(
                    db,
                    user_id=user.id,
                    relative_path=rel,
                    dest_folder=TARGET,
                    new_title=None if dest_name == path.name else dest_name.replace(".md", ""),
                )
                moved += 1
                print(f"  moved: {rel} -> {dest_rel}")
            except Exception as exc:
                print(f"  skip {rel}: {exc}")

        print(f"Done — moved {moved} note(s) into {TARGET}/")
    finally:
        db.close()


if __name__ == "__main__":
    main()
