"""Tests for unified app logging."""

from pathlib import Path

from backend.core.log_setup import list_log_files, resolve_log_path, setup_logging, tail_log_file


def test_setup_logging_creates_backend_log(tmp_path, monkeypatch):
    monkeypatch.setattr("backend.core.log_setup.LOGS_DIR", tmp_path)
    monkeypatch.setattr("backend.core.log_setup._BACKEND_LOG", tmp_path / "backend.log")
    monkeypatch.setattr("backend.core.log_setup._NOTES_LOG", tmp_path / "notes_generation.log")
    monkeypatch.setattr("backend.core.log_setup._CONFIGURED", False)

    setup_logging()
    assert (tmp_path / "backend.log").is_file()


def test_resolve_log_path_rejects_traversal(tmp_path, monkeypatch):
    monkeypatch.setattr("backend.core.log_setup.LOGS_DIR", tmp_path)
    try:
        resolve_log_path("../secret.log")
        assert False, "expected ValueError"
    except ValueError:
        pass


def test_tail_missing_log():
    text = tail_log_file("does_not_exist_yet.log")
    assert "not found" in text.lower()


def test_list_log_files_includes_known_names(tmp_path, monkeypatch):
    monkeypatch.setattr("backend.core.log_setup.LOGS_DIR", tmp_path)
    monkeypatch.setattr("backend.core.log_setup._BACKEND_LOG", tmp_path / "backend.log")
    monkeypatch.setattr("backend.core.log_setup._NOTES_LOG", tmp_path / "notes_generation.log")
    (tmp_path / "backend.log").write_text("hello\n", encoding="utf-8")
    names = {item["name"] for item in list_log_files()}
    assert "backend.log" in names


def test_tail_reads_only_last_lines(tmp_path, monkeypatch):
    monkeypatch.setattr("backend.core.log_setup.LOGS_DIR", tmp_path)
    log_path = tmp_path / "backend.log"
    log_path.write_text("\n".join(f"line-{i}" for i in range(500)), encoding="utf-8")
    text = tail_log_file("backend.log", max_lines=3)
    assert text.splitlines() == ["line-497", "line-498", "line-499"]
