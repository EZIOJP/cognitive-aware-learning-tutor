"""Move every file under data/notes/ into the library root and remove subfolders."""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.db import SessionLocal
from backend.models import User
from backend.paths import NOTES_DIR
from backend.transcripts.library import move_note
from backend.transcripts.path_utils import build_relative_path, normalize_filename


def _unique_dest_name(dest_dir: Path, name: str, *, prefix: str) -> str:
    candidate = dest_dir / name
    if not candidate.exists():
        return name
    stem = Path(name).stem
    suffix = Path(name).suffix
    tagged = f"{prefix}_{stem}{suffix}" if prefix else f"{stem}_copy{suffix}"
    if not (dest_dir / tagged).exists():
        return tagged
    n = 2
    while (dest_dir / f"{prefix}_{stem}_{n}{suffix}").exists():
        n += 1
    return f"{prefix}_{stem}_{n}{suffix}"


def _remove_empty_dirs(base: Path) -> int:
    removed = 0
    for path in sorted(base.rglob("*"), key=lambda p: len(p.parts), reverse=True):
        if path == base:
            continue
        if path.is_dir() and not any(path.iterdir()):
            path.rmdir()
            removed += 1
    return removed


def main() -> None:
    NOTES_DIR.mkdir(parents=True, exist_ok=True)

    nested_files = sorted(
        p
        for p in NOTES_DIR.rglob("*")
        if p.is_file() and p.parent != NOTES_DIR and not p.name.startswith(".")
    )
    if not nested_files:
        removed = _remove_empty_dirs(NOTES_DIR)
        print(f"No nested files. Removed {removed} empty folder(s).")
        return

    db = SessionLocal()
    try:
        user = db.query(User).order_by(User.id).first()
        if not user:
            print("No user in database — files will move on disk only.")

        moved = 0
        for path in nested_files:
            rel = path.relative_to(NOTES_DIR).as_posix()
            parent_tag = path.parent.name.replace(" ", "_")[:40]
            dest_name = _unique_dest_name(NOTES_DIR, path.name, prefix=parent_tag)
            dest_rel = build_relative_path("", dest_name)
            dest_path = NOTES_DIR / dest_name

            if path.suffix.lower() == ".md" and user:
                try:
                    move_note(
                        db,
                        user_id=user.id,
                        relative_path=rel,
                        dest_folder="",
                        new_title=None if dest_name == path.name else Path(dest_name).stem,
                    )
                    moved += 1
                    print(f"  md: {rel} -> {dest_rel}")
                    continue
                except Exception as exc:
                    print(f"  move_note failed for {rel} ({exc}), falling back to shutil")

            dest_path = NOTES_DIR / dest_name
            if dest_path.exists():
                dest_name = _unique_dest_name(NOTES_DIR, path.name, prefix=f"{parent_tag}_dup")
                dest_path = NOTES_DIR / dest_name
                dest_rel = dest_name

            shutil.move(str(path), str(dest_path))
            moved += 1
            print(f"  file: {rel} -> {dest_rel}")

        removed = _remove_empty_dirs(NOTES_DIR)
        print(f"Done — moved {moved} file(s) to notes root, removed {removed} empty folder(s).")
    finally:
        db.close()


if __name__ == "__main__":
    main()
