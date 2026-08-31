"""Tests for study library file/folder management."""

import time

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.models.study import Base, LectureNote
from backend.transcripts.library import (
    NOTES_DIR,
    build_library_tree,
    create_folder,
    create_note_file,
    delete_folder,
    delete_note,
    move_note,
    sync_disk_notes_for_user,
    update_reading_state,
)
from backend.transcripts.note_topics import remap_legacy_note_path


@pytest.fixture()
def db(tmp_path, monkeypatch):
    notes_dir = tmp_path / "notes"
    notes_dir.mkdir()
    monkeypatch.setattr("backend.transcripts.library.NOTES_DIR", notes_dir)
    monkeypatch.setattr("backend.paths.NOTES_DIR", notes_dir)

    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


def test_move_note_and_reading_state(db):
    row = create_note_file(db, user_id=1, title="Alpha", folder_path="", kind="note", content="# A\n")
    rel = row.relative_path or row.filename
    create_folder("lectures")
    moved = move_note(db, user_id=1, relative_path=rel, dest_folder="lectures")
    assert moved.folder_path == "lectures"
    assert moved.relative_path.startswith("lectures/")

    state = update_reading_state(db, user_id=1, relative_path=moved.relative_path, read_scroll_top=420)
    assert state["read_scroll_top"] == 420

    state2 = update_reading_state(
        db,
        user_id=1,
        relative_path=moved.relative_path,
        read_scroll_top=500,
        set_bookmark_from_read=True,
    )
    assert state2["bookmark_scroll_top"] == 500

    tree = build_library_tree(db, 1)
    files = tree["root"]["folders"][0]["files"]
    assert any(f["relative_path"] == moved.relative_path and f["read_scroll_top"] == 500 for f in files)


def test_delete_note_and_folder(db):
    create_folder("temp")
    row = create_note_file(
        db,
        user_id=1,
        title="ToDelete",
        folder_path="temp",
        kind="note",
        content="# x\n",
    )
    rel = row.relative_path or row.filename
    delete_note(db, user_id=1, relative_path=rel)
    assert db.query(LectureNote).filter(LectureNote.user_id == 1).count() == 0

    create_note_file(db, user_id=1, title="Inner", folder_path="temp", kind="note", content="# y\n")
    delete_folder(db, user_id=1, folder_path="temp")
    assert not (NOTES_DIR / "temp").exists()
    assert db.query(LectureNote).filter(LectureNote.user_id == 1).count() == 0


def test_save_note_content(db):
    import backend.transcripts.library as lib
    from backend.transcripts.library import save_note_content

    row = create_note_file(db, user_id=1, title="Editable", folder_path="", kind="note", content="# Old\n")
    rel = row.relative_path or row.filename
    updated = save_note_content(
        db,
        user_id=1,
        relative_path=rel,
        content="# Updated title\n\n```python\nprint(1)\n```\n",
    )
    assert updated.section_count >= 1
    path = lib.NOTES_DIR / rel
    assert path.is_file()
    assert "Updated title" in path.read_text(encoding="utf-8")


def test_sync_skips_legacy_remap_when_canonical_filename_occupied(db):
    """Legacy lecture_N paths must not overwrite an existing canonical row."""
    import backend.transcripts.library as lib

    canonical = "data_foundations/lecture_2/full_lenght_2_notes.md"
    legacy = "lecture_2/full_lenght_2_notes.md"
    assert remap_legacy_note_path(legacy) == canonical

    dest = lib.NOTES_DIR / canonical
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text("# lecture 2\n", encoding="utf-8")

    now = int(time.time())
    canonical_row = LectureNote(
        user_id=1,
        filename=canonical,
        relative_path=canonical,
        folder_path="data_foundations/lecture_2",
        kind="lecture",
        title="Canonical",
        source="disk",
        section_count=1,
        created_at=now,
    )
    legacy_row = LectureNote(
        user_id=1,
        filename=legacy,
        relative_path=legacy,
        folder_path="lecture_2",
        kind="lecture",
        title="Legacy",
        source="disk",
        section_count=1,
        created_at=now,
    )
    db.add_all([canonical_row, legacy_row])
    db.commit()

    sync_disk_notes_for_user(db, 1)
    db.refresh(canonical_row)
    db.refresh(legacy_row)

    assert canonical_row.filename == canonical
    assert legacy_row.filename == legacy
    tree = build_library_tree(db, 1)
    assert tree["root"]["name"] == "Library"


def test_sync_remaps_legacy_when_canonical_unoccupied(db):
    import backend.transcripts.library as lib

    canonical = "data_foundations/lecture_2/numpy_lecture_notes.md"
    legacy = "lecture_2/numpy_lecture_notes.md"
    dest = lib.NOTES_DIR / canonical
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text("# numpy\n", encoding="utf-8")

    now = int(time.time())
    row = LectureNote(
        user_id=1,
        filename=legacy,
        relative_path=legacy,
        folder_path="lecture_2",
        kind="lecture",
        title="Legacy numpy",
        source="disk",
        section_count=1,
        created_at=now,
    )
    db.add(row)
    db.commit()

    sync_disk_notes_for_user(db, 1)
    db.refresh(row)
    assert row.filename == canonical
    assert row.relative_path == canonical


def test_library_tree_for_user_rolls_back_integrity_error(db, monkeypatch):
    from sqlalchemy.exc import IntegrityError

    from backend.transcripts.library import library_tree_for_user

    def boom(*_a, **_k):
        raise IntegrityError("UNIQUE", {}, Exception("UNIQUE"))

    monkeypatch.setattr("backend.transcripts.library.sync_disk_notes_for_user", boom)
    tree = library_tree_for_user(db, 1)
    assert tree["root"]["name"] == "Library"
