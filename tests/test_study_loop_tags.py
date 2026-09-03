import json
from pathlib import Path

from backend.quiz import tag_index as ti
from backend.quiz.content_bank import Catalog


def test_list_tags_includes_note_and_question(tmp_path: Path, monkeypatch):
    notes = tmp_path / "notes"
    notes.mkdir()
    (notes / "L05.md").write_text(
        "## `L5-T05` — Unique\n\nBody here is long enough.\n",
        encoding="utf-8",
    )
    qdir = tmp_path / "questions" / "math" / "x"
    qdir.mkdir(parents=True)
    (qdir / "pack.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "kind": "math",
                "topic": {
                    "topic_id": "math.demo.unique",
                    "title": "Unique",
                    "note_topic_ids": ["L5-T05"],
                    "path": [],
                },
                "questions": [
                    {
                        "id": "math.demo.unique.q001",
                        "problem": "1+1",
                        "answer": "2",
                        "tags": ["warmup"],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(ti, "NOTES_DIR", notes)
    monkeypatch.setattr(ti, "QUESTIONS_DIR", tmp_path / "questions")
    tags = {t["id"]: t for t in ti.list_tags()}
    assert "L5-T05" in tags
    assert tags["L5-T05"]["has_read_card"] is True
    assert tags["L5-T05"]["question_count"] >= 1
    assert "warmup" in tags


def test_merge_free_into_note_topic(tmp_path: Path, monkeypatch):
    qdir = tmp_path / "questions" / "math" / "x"
    qdir.mkdir(parents=True)
    path = qdir / "pack.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "kind": "math",
                "topic": {
                    "topic_id": "math.demo.merge",
                    "title": "Merge",
                    "note_topic_ids": ["L5-T05"],
                    "path": [],
                },
                "questions": [
                    {
                        "id": "math.demo.merge.q001",
                        "problem": "x",
                        "answer": "1",
                        "tags": ["oldfree"],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(ti, "QUESTIONS_DIR", tmp_path / "questions")
    monkeypatch.setattr(ti, "NOTES_DIR", tmp_path / "notes")
    (tmp_path / "notes").mkdir()
    result = ti.merge_tags("oldfree", "L5-T05")
    # CRITICAL: source JSON must change on disk (Approach A / wire-don't-migrate)
    disk = json.loads(path.read_text(encoding="utf-8"))
    assert "oldfree" not in disk["questions"][0]["tags"]
    assert "L5-T05" in disk["questions"][0]["tags"]
    assert result["refs_updated"] >= 1


def test_vocab_group_tag_listed(monkeypatch):
    monkeypatch.setattr(
        ti,
        "load_words",
        lambda db=None: [
            {"id": 1, "word": "abate", "group_number": 2, "tags": ["emotion"]},
            {"id": 2, "word": "chicanery", "group_number": 2, "tags": []},
        ],
    )
    monkeypatch.setattr(ti, "list_read_cards", lambda **kw: [])
    monkeypatch.setattr(ti, "load_catalog", lambda **kw: Catalog())
    tags = {t["id"]: t for t in ti.list_tags()}
    assert tags["vocab.group.2"]["vocab_count"] == 2
    assert tags["emotion"]["vocab_count"] == 1


def test_add_tag_appends_word_tags(monkeypatch):
    words = [
        {"id": 1, "word": "abate", "group_number": 2, "tags": []},
        {"id": 2, "word": "chicanery", "group_number": 2, "tags": ["emotion"]},
    ]
    monkeypatch.setattr(ti, "load_words", lambda db=None: words)
    monkeypatch.setattr(ti, "save_words", lambda w, db=None: None)
    monkeypatch.setattr(ti, "list_read_cards", lambda **kw: [])
    monkeypatch.setattr(ti, "load_catalog", lambda **kw: Catalog())
    out = ti.add_tag("emotion", word_ids=[1])
    assert "emotion" in words[0]["tags"]
    assert out["vocab_count"] >= 1
    assert out["refs_updated"] == 1
