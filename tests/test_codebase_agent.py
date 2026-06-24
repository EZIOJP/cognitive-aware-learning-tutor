import pytest

from backend.hub.services.codebase_agent import (
    build_codebase_snapshot,
    list_browse_files,
    read_project_file,
    retrieve_codebase_knowledge,
    search_codebase,
)


def test_build_codebase_snapshot_has_routes():
    snap = build_codebase_snapshot(force=True)
    assert snap["scanned_files"] > 50
    routes = snap["frontend_routes"]
    assert any("lecture-notes" in r for r in routes)
    assert snap["api_route_count"] > 5
    assert snap["study_pipeline"]["step1_live_captions"] is True


def test_search_codebase_finds_lecture_files():
    hits = search_codebase("LectureNotesPage markdown", max_files=4)
    paths = [h["path"] for h in hits]
    assert any("LectureNotes" in p or "MarkdownNote" in p for p in paths)


def test_read_project_file_safe():
    data = read_project_file("run.bat")
    assert "run" in data["content"].lower()


def test_read_project_file_rejects_traversal():
    with pytest.raises((ValueError, FileNotFoundError)):
        read_project_file("not/a/real/../../../secret")


def test_list_browse_files_prefix():
    files = list_browse_files("MarkdownNote")
    assert any("MarkdownNote" in f for f in files)


def test_retrieve_codebase_knowledge_bounded():
    kb = retrieve_codebase_knowledge("study-library css gloss-panel")
    assert "snapshot" in kb
    assert "matched_files" in kb
    assert len(str(kb)) < 25_000
