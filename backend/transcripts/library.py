"""Study library — folders and note files under data/notes/."""

from __future__ import annotations

import re
import shutil
import time
from pathlib import Path
from typing import Any, Literal

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.models.study import LectureNote
from backend.paths import NOTES_DIR, NOTES_RULES_DIRNAME
from backend.transcripts.notes_generator import resolve_notes_path
from backend.transcripts.path_utils import (
    build_relative_path,
    normalize_filename,
    normalize_folder_path,
)

NoteKind = Literal["lecture", "textbook", "quiz", "exercise", "note"]
VALID_KINDS = frozenset({"lecture", "textbook", "quiz", "exercise", "note"})

# library/tree was timing out under poll storms — throttle disk sync + cache tree briefly.
_SYNC_MIN_INTERVAL_S = 60.0
_TREE_TTL_S = 15.0
_last_sync_mono: dict[int, float] = {}
_tree_cache: dict[int, tuple[float, dict[str, Any]]] = {}


def invalidate_library_tree_cache(user_id: int | None = None) -> None:
    if user_id is None:
        _tree_cache.clear()
        return
    _tree_cache.pop(int(user_id), None)


def note_storage_path(row: LectureNote) -> str:
    return (row.relative_path or row.filename or "").replace("\\", "/")


def is_indexable_library_note(relative_path: str) -> bool:
    """Lecture library UI/search — skip meta/rules folder under data/notes/rules/."""
    rel = relative_path.replace("\\", "/").lstrip("/")
    if not rel.lower().endswith(".md"):
        return False
    if rel.startswith(f"{NOTES_RULES_DIRNAME}/"):
        return False
    return True


def list_disk_folders() -> list[str]:
    folders, _mds = _scan_notes_disk()
    return sorted(folders)


def _scan_notes_disk() -> tuple[set[str], list[tuple[str, float]]]:
    """One filesystem walk: folder paths + indexable markdown (rel, mtime)."""
    NOTES_DIR.mkdir(parents=True, exist_ok=True)
    folders: set[str] = set()
    mds: list[tuple[str, float]] = []
    for p in NOTES_DIR.rglob("*"):
        try:
            if p.is_dir() and p != NOTES_DIR:
                rel = p.relative_to(NOTES_DIR).as_posix()
                if rel.split("/")[0] == NOTES_RULES_DIRNAME:
                    continue
                folders.add(rel)
                parts = rel.split("/")
                for i in range(1, len(parts)):
                    folders.add("/".join(parts[:i]))
            elif p.is_file() and p.suffix.lower() == ".md":
                rel = p.relative_to(NOTES_DIR).as_posix()
                if not is_indexable_library_note(rel):
                    continue
                mds.append((rel, p.stat().st_mtime))
        except OSError:
            continue
    return folders, mds


def _folder_from_relative(rel: str) -> str:
    parts = rel.replace("\\", "/").split("/")
    if len(parts) <= 1:
        return ""
    return "/".join(parts[:-1])


def _title_from_relative(rel: str) -> str:
    stem = Path(rel).stem
    return stem.replace("_", " ").strip() or stem


def merge_disk_files_into_tree(files_by_folder: dict[str, list[dict[str, Any]]], indexed: set[str]) -> None:
    """Show markdown on disk even when not indexed for the current user."""
    _folders, mds = _scan_notes_disk()
    for rel, mtime in mds:
        if rel in indexed:
            continue
        folder = _folder_from_relative(rel)
        files_by_folder.setdefault(folder, []).append(
            {
                "relative_path": rel,
                "title": _title_from_relative(rel),
                "kind": "lecture",
                "topic": None,
                "source": "disk",
                "created_at": int(mtime),
                "read_scroll_top": 0,
                "bookmark_scroll_top": None,
            }
        )


def sync_disk_notes_for_user(db: Session, user_id: int, *, force: bool = False) -> int:
    """Index unowned on-disk markdown into the current user's library."""
    from backend.transcripts.note_topics import remap_legacy_note_path

    # Remap old lecture_N / lecture5 paths after the data_foundations move.
    # LectureNote.filename is globally unique — skip if another row already
    # owns the canonical path (legacy + remapped duplicates).
    occupied: set[str] = set()
    for r in db.query(LectureNote).all():
        if r.filename:
            occupied.add(r.filename.replace("\\", "/"))
        if r.relative_path:
            occupied.add(r.relative_path.replace("\\", "/"))

    for row in db.query(LectureNote).filter(LectureNote.user_id == user_id).all():
        old = (row.relative_path or row.filename or "").replace("\\", "/")
        new = remap_legacy_note_path(old)
        if new == old or not (NOTES_DIR / new).is_file():
            continue
        if new in occupied:
            continue
        occupied.discard(old)
        occupied.add(new)
        row.relative_path = new
        row.filename = new
        row.folder_path = _folder_from_relative(new)
    db.commit()

    now = time.monotonic()
    last = _last_sync_mono.get(int(user_id), 0.0)
    if not force and (now - last) < _SYNC_MIN_INTERVAL_S:
        return 0

    indexed_global = {
        (r.relative_path or r.filename or "").replace("\\", "/")
        for r in db.query(LectureNote).all()
    }
    added = 0
    _folders, mds = _scan_notes_disk()
    for rel, mtime in sorted(mds, key=lambda t: t[1], reverse=True):
        if rel in indexed_global:
            continue
        folder = _folder_from_relative(rel)
        title = _title_from_relative(rel)
        # Avoid reading full file bodies on every sync — section_count is cheap later.
        row = LectureNote(
            user_id=user_id,
            filename=rel,
            relative_path=rel,
            folder_path=folder,
            kind="lecture",
            title=title,
            topic=None,
            source="disk",
            section_count=1,
            created_at=int(mtime),
        )
        db.add(row)
        indexed_global.add(rel)
        added += 1
    if added:
        db.commit()
    _last_sync_mono[int(user_id)] = time.monotonic()
    return added


def library_tree_for_user(db: Session, user_id: int) -> dict[str, Any]:
    """Sync disk notes then return the tree; never fail the library UI on remap collisions."""
    uid = int(user_id)
    now = time.monotonic()
    hit = _tree_cache.get(uid)
    if hit is not None and (now - hit[0]) < _TREE_TTL_S:
        return hit[1]
    try:
        sync_disk_notes_for_user(db, user_id)
    except IntegrityError:
        db.rollback()
    tree = build_library_tree(db, user_id)
    _tree_cache[uid] = (time.monotonic(), tree)
    return tree


def build_library_tree(db: Session, user_id: int) -> dict[str, Any]:
    rows = db.query(LectureNote).filter(LectureNote.user_id == user_id).all()
    disk_folders, disk_mds = _scan_notes_disk()
    db_folders = {normalize_folder_path(r.folder_path or "") for r in rows}
    db_folders.update(disk_folders)

    files_by_folder: dict[str, list[dict[str, Any]]] = {}
    indexed: set[str] = set()
    for row in rows:
        folder = normalize_folder_path(row.folder_path or "")
        rel = note_storage_path(row)
        indexed.add(rel)
        files_by_folder.setdefault(folder, []).append(
            {
                "relative_path": rel,
                "title": row.title,
                "kind": row.kind or "lecture",
                "topic": row.topic,
                "source": row.source,
                "created_at": row.created_at,
                "read_scroll_top": row.read_scroll_top or 0,
                "bookmark_scroll_top": row.bookmark_scroll_top,
            }
        )

    for rel, mtime in disk_mds:
        if rel in indexed:
            continue
        folder = _folder_from_relative(rel)
        files_by_folder.setdefault(folder, []).append(
            {
                "relative_path": rel,
                "title": _title_from_relative(rel),
                "kind": "lecture",
                "topic": None,
                "source": "disk",
                "created_at": int(mtime),
                "read_scroll_top": 0,
                "bookmark_scroll_top": None,
            }
        )

    for folder in disk_folders:
        db_folders.add(folder)
    for folder in files_by_folder:
        if folder:
            db_folders.add(folder)
            parts = folder.split("/")
            for i in range(1, len(parts)):
                db_folders.add("/".join(parts[:i]))

    def folder_node(path: str) -> dict[str, Any]:
        children_paths = sorted(
            f for f in db_folders if f and f.startswith(f"{path}/") and f.count("/") == path.count("/") + 1
        )
        return {
            "path": path,
            "name": path.split("/")[-1] if path else "Library",
            "folders": [folder_node(c) for c in children_paths],
            "files": sorted(files_by_folder.get(path, []), key=lambda x: x["title"].lower()),
        }

    root_folders = sorted(f for f in db_folders if f and "/" not in f)
    return {
        "root": {
            "path": "",
            "name": "Library",
            "folders": [folder_node(f) for f in root_folders],
            "files": sorted(files_by_folder.get("", []), key=lambda x: x["title"].lower()),
        }
    }


def create_folder(folder_path: str) -> str:
    path = normalize_folder_path(folder_path)
    target = NOTES_DIR / path if path else NOTES_DIR
    target.mkdir(parents=True, exist_ok=True)
    return path


def create_note_file(
    db: Session,
    *,
    user_id: int,
    title: str,
    folder_path: str = "",
    kind: str = "note",
    content: str | None = None,
    topic: str | None = None,
) -> LectureNote:
    if kind not in VALID_KINDS:
        raise ValueError(f"Invalid kind: {kind}")
    folder = normalize_folder_path(folder_path)
    if folder:
        (NOTES_DIR / folder).mkdir(parents=True, exist_ok=True)

    stamp = time.strftime("%Y%m%d_%H%M%S")
    safe_title = "".join(c if c.isalnum() or c in "-_ " else "_" for c in title)[:50].strip() or "Untitled"
    filename = normalize_filename(f"{safe_title}_{stamp}.md")
    relative = build_relative_path(folder, filename)
    disk_path = (NOTES_DIR / relative).resolve()
    if not disk_path.is_relative_to(NOTES_DIR.resolve()):
        raise ValueError("Invalid note path")

    body = content if content is not None else f"# {title.strip() or 'Untitled'}\n\n"
    disk_path.parent.mkdir(parents=True, exist_ok=True)
    disk_path.write_text(body, encoding="utf-8")

    section_count = body.count("\n## ") + (1 if body.startswith("## ") else 0)
    row = LectureNote(
        user_id=user_id,
        filename=relative,
        relative_path=relative,
        folder_path=folder,
        kind=kind,
        title=title.strip() or safe_title,
        topic=topic,
        source="manual",
        section_count=max(1, section_count),
        created_at=int(time.time()),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    invalidate_library_tree_cache(user_id)
    return row


def _find_note_row(db: Session, user_id: int, relative_path: str) -> LectureNote | None:
    rel = relative_path.replace("\\", "/")
    return (
        db.query(LectureNote)
        .filter(LectureNote.user_id == user_id)
        .filter((LectureNote.relative_path == rel) | (LectureNote.filename == rel))
        .first()
    )


def _find_note_row_by_path(db: Session, relative_path: str) -> LectureNote | None:
    rel = relative_path.replace("\\", "/")
    return (
        db.query(LectureNote)
        .filter((LectureNote.relative_path == rel) | (LectureNote.filename == rel))
        .first()
    )


def index_note_from_disk(db: Session, user_id: int, relative_path: str) -> LectureNote:
    rel = relative_path.replace("\\", "/")
    existing = _find_note_row(db, user_id, rel)
    if existing:
        return existing
    existing_any = _find_note_row_by_path(db, rel)
    if existing_any:
        return existing_any
    path = resolve_notes_path(rel)
    if not path.is_file():
        raise FileNotFoundError("Note file not found on disk.")
    try:
        content = path.read_text(encoding="utf-8")
    except OSError:
        content = ""
    folder = _folder_from_relative(rel)
    title = _title_from_relative(rel)
    section_count = content.count("\n## ") + (1 if content.startswith("## ") else 0)
    row = LectureNote(
        user_id=user_id,
        filename=rel,
        relative_path=rel,
        folder_path=folder,
        kind="lecture",
        title=title,
        topic=None,
        source="disk",
        section_count=max(1, section_count),
        created_at=int(path.stat().st_mtime),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def delete_note(db: Session, *, user_id: int, relative_path: str) -> None:
    rel = relative_path.replace("\\", "/")
    row = _find_note_row(db, user_id, rel)
    try:
        path = (NOTES_DIR / rel).resolve()
        if path.is_file() and path.is_relative_to(NOTES_DIR.resolve()):
            path.unlink()
    except (ValueError, OSError):
        pass
    if row:
        db.delete(row)
        db.commit()
    invalidate_library_tree_cache(user_id)


def delete_folder(db: Session, *, user_id: int, folder_path: str) -> int:
    folder = normalize_folder_path(folder_path)
    if not folder:
        raise ValueError("Cannot delete library root.")
    target = NOTES_DIR / folder
    if not target.exists():
        raise FileNotFoundError("Folder not found.")
    removed = 0
    prefix = f"{folder}/"
    rows = db.query(LectureNote).filter(LectureNote.user_id == user_id).all()
    for row in list(rows):
        rel = note_storage_path(row)
        if rel == folder or rel.startswith(prefix):
            db.delete(row)
            removed += 1
    shutil.rmtree(target)
    db.commit()
    invalidate_library_tree_cache(user_id)
    return removed


def update_reading_state(
    db: Session,
    *,
    user_id: int,
    relative_path: str,
    read_scroll_top: int | None = None,
    bookmark_scroll_top: int | None = None,
    set_bookmark_from_read: bool = False,
) -> dict[str, int | None]:
    row = _find_note_row(db, user_id, relative_path)
    if not row:
        row = _find_note_row_by_path(db, relative_path)
    if not row:
        row = index_note_from_disk(db, user_id, relative_path)
    if read_scroll_top is not None:
        row.read_scroll_top = max(0, int(read_scroll_top))
    if set_bookmark_from_read:
        row.bookmark_scroll_top = row.read_scroll_top
    elif bookmark_scroll_top is not None:
        row.bookmark_scroll_top = max(0, int(bookmark_scroll_top))
    row.updated_at = int(time.time())
    db.commit()
    db.refresh(row)
    return {
        "read_scroll_top": row.read_scroll_top,
        "bookmark_scroll_top": row.bookmark_scroll_top,
    }


def list_notes_in_folder(folder_path: str, *, recursive: bool = True) -> list[str]:
    folder = normalize_folder_path(folder_path)
    base = NOTES_DIR / folder if folder else NOTES_DIR
    if not base.exists():
        return []
    paths: list[str] = []
    globber = base.rglob("*.md") if recursive else base.glob("*.md")
    for md in sorted(globber):
        if md.is_file():
            rel = md.relative_to(NOTES_DIR).as_posix()
            if not recursive and _folder_from_relative(rel) != folder:
                continue
            paths.append(rel)
    return paths


def move_note(
    db: Session,
    *,
    user_id: int,
    relative_path: str,
    dest_folder: str,
    new_title: str | None = None,
) -> LectureNote:
    rel = relative_path.replace("\\", "/")
    row = _find_note_row(db, user_id, rel)
    if not row:
        row = _find_note_row_by_path(db, rel)
    if not row:
        row = index_note_from_disk(db, user_id, rel)

    dest = normalize_folder_path(dest_folder)
    if dest:
        (NOTES_DIR / dest).mkdir(parents=True, exist_ok=True)

    old_path = resolve_notes_path(note_storage_path(row))
    if not old_path.is_file():
        raise FileNotFoundError("Note file missing on disk.")

    basename = old_path.name
    if new_title:
        basename = normalize_filename(new_title)

    new_rel = build_relative_path(dest, basename)
    new_path = (NOTES_DIR / new_rel).resolve()
    if not new_path.is_relative_to(NOTES_DIR.resolve()):
        raise ValueError("Invalid destination path")

    if new_path != old_path:
        if new_path.exists():
            raise ValueError("A file already exists at the destination.")
        shutil.move(str(old_path), str(new_path))

    row.folder_path = dest
    row.relative_path = new_rel
    row.filename = new_rel
    if new_title:
        row.title = new_title.strip()
    db.commit()
    db.refresh(row)
    invalidate_library_tree_cache(user_id)
    return row


def update_note_meta(
    db: Session,
    *,
    user_id: int,
    relative_path: str,
    kind: str | None = None,
    title: str | None = None,
    topic: str | None = None,
) -> LectureNote:
    rel = relative_path.replace("\\", "/")
    row = (
        db.query(LectureNote)
        .filter(LectureNote.user_id == user_id)
        .filter((LectureNote.relative_path == rel) | (LectureNote.filename == rel))
        .first()
    )
    if not row:
        raise FileNotFoundError("Note not found.")
    if kind is not None:
        if kind not in VALID_KINDS:
            raise ValueError(f"Invalid kind: {kind}")
        row.kind = kind
    if title is not None and title.strip():
        row.title = title.strip()
    if topic is not None:
        row.topic = topic.strip() or None
    db.commit()
    db.refresh(row)
    return row


def search_library_notes(
    db: Session,
    user_id: int,
    query: str,
    *,
    limit: int = 60,
    kinds: set[str] | None = None,
) -> list[dict[str, Any]]:
    """Topic + function + text search across all library markdown."""
    from backend.transcripts.note_search import search_all_notes
    from backend.transcripts.library import note_storage_path

    q = query.strip()
    if not q:
        return []

    title_by_basename: dict[str, str] = {}
    for row in db.query(LectureNote).filter(LectureNote.user_id == user_id).all():
        rel = note_storage_path(row)
        title_by_basename[Path(rel).name.lower()] = row.title or _title_from_relative(rel)

    note_files: list[tuple[str, str, str]] = []
    seen: set[str] = set()

    NOTES_DIR.mkdir(parents=True, exist_ok=True)
    for md in sorted(NOTES_DIR.rglob("*.md")):
        name = md.name.lower()
        if not name.endswith(".md") or name.startswith(".") or ".bak" in name:
            continue
        rel = md.relative_to(NOTES_DIR).as_posix()
        if not is_indexable_library_note(rel):
            continue
        if rel in seen:
            continue
        seen.add(rel)
        title = title_by_basename.get(md.name.lower()) or _title_from_relative(rel)
        note_files.append((rel, title, "lecture"))

    return search_all_notes(note_files, q, limit=limit, kinds=kinds)


def save_note_content(
    db: Session,
    *,
    user_id: int,
    relative_path: str,
    content: str,
) -> LectureNote:
    rel = relative_path.replace("\\", "/")
    row = _find_note_row(db, user_id, rel)
    if not row:
        row = index_note_from_disk(db, user_id, rel)

    disk_path = (NOTES_DIR / rel).resolve()
    if not disk_path.is_relative_to(NOTES_DIR.resolve()):
        raise ValueError("Invalid note path.")

    from backend.transcripts.note_lint import sanitize_note_content

    content = sanitize_note_content(content)

    disk_path.parent.mkdir(parents=True, exist_ok=True)
    disk_path.write_text(content, encoding="utf-8")

    section_count = content.count("\n## ") + (1 if content.startswith("## ") else 0)
    row.section_count = max(1, section_count)
    row.updated_at = int(time.time())
    db.commit()
    db.refresh(row)
    return row
