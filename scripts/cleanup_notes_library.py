#!/usr/bin/env python3
"""Flatten data/notes: rename lecture files serially, delete junk, purge stale DB rows."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.db.session import SessionLocal
from backend.models.study import LectureNote
from backend.paths import NOTES_DIR
from backend.transcripts.library import sync_disk_notes_for_user

# Lecture number + topic serial names (root only)
RENAMES: dict[str, str] = {
    "numpy_lecture_notes.md": "L02_numpy_operations_notes.md",
    "numpy_lecture3_notes.md": "L03_numpy_lecture3_notes.md",
    "lecture4_vectorization_stacking_pandas_notes.md": "L04_vectorization_stacking_pandas_notes.md",
    "lecture5 pandas operations notes _3__20260902_165511.md": "L05_pandas_operations_notes.md",
}

KEEP_LECTURE_MD = set(RENAMES.values())

DELETE_GLOBS = ("*.pdf", "*.ipynb")


def main() -> None:
    NOTES_DIR.mkdir(parents=True, exist_ok=True)

    # 1. Rename lecture notes
    for old_name, new_name in RENAMES.items():
        src = NOTES_DIR / old_name
        dst = NOTES_DIR / new_name
        if src.is_file():
            if dst.is_file() and dst != src:
                dst.unlink()
            src.rename(dst)
            print(f"renamed: {old_name} -> {new_name}")
        elif dst.is_file():
            print(f"already: {new_name}")
        else:
            print(f"missing: {old_name}")

    # 2. Delete non-markdown junk in root
    for pattern in DELETE_GLOBS:
        for path in NOTES_DIR.glob(pattern):
            path.unlink()
            print(f"deleted: {path.name}")

    # 3. Remove empty subfolders (keep data/notes/rules/)
    for path in sorted(NOTES_DIR.rglob("*"), reverse=True):
        if path.is_dir() and path != NOTES_DIR:
            try:
                path.rmdir()
                print(f"removed dir: {path.relative_to(NOTES_DIR)}")
            except OSError:
                pass

    # 4. Purge stale DB index (ghost folders + missing files)
    db = SessionLocal()
    try:
        rows = db.query(LectureNote).all()
        removed = 0
        for row in rows:
            rel = (row.relative_path or row.filename or "").replace("\\", "/")
            disk = NOTES_DIR / rel if rel else None
            basename = Path(rel).name if rel else ""
            in_keep = basename in KEEP_LECTURE_MD and "/" not in rel
            on_disk = disk.is_file() if disk else False
            if not in_keep or not on_disk or "/" in rel:
                db.delete(row)
                removed += 1
        db.commit()
        print(f"DB: removed {removed} stale lecture_notes rows")

        user_ids = {r.user_id for r in db.query(LectureNote.user_id).distinct()}
        if not user_ids:
            user_ids = {1}
        for uid in user_ids:
            added = sync_disk_notes_for_user(db, uid)
            if added:
                print(f"DB: indexed {added} disk files for user {uid}")

        # Fix folder_path for root files
        for row in db.query(LectureNote).all():
            rel = (row.relative_path or row.filename or "").replace("\\", "/")
            if row.folder_path != "" and "/" not in rel:
                row.folder_path = ""
                row.filename = rel
                row.relative_path = rel
        db.commit()
        print("DB: folder paths flattened to root")
    finally:
        db.close()

    print("\nFinal root files:")
    for p in sorted(NOTES_DIR.glob("*")):
        if p.is_file():
            print(f"  {p.name}")


if __name__ == "__main__":
    main()
