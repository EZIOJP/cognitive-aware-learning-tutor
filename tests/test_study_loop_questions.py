from pathlib import Path

from backend.quiz import question_crud as qc


def test_create_and_patch_open_math(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(qc, "QUESTIONS_DIR", tmp_path)
    created = qc.upsert_question(
        {
            "kind": "math",
            "topic_id": "math.loop.demo",
            "topic_title": "Demo",
            "note_topic_ids": ["MT1-T02"],
            "question": {
                "id": "math.loop.demo.q001",
                "problem": "Prove something",
                "answer": "",
                "answer_format": "open",
                "tags": ["no-answer"],
            },
        }
    )
    assert created["id"] == "math.loop.demo.q001"
    patched = qc.patch_question(
        "math.loop.demo.q001",
        {"answer": "42", "answer_format": "number", "solution_steps": ["step"], "tags": []},
    )
    assert patched["answer"] == "42"
    assert patched["answer_format"] == "number"
    items = qc.list_questions(tag="MT1-T02", kind="math")
    assert any(i["id"] == "math.loop.demo.q001" for i in items)


def test_import_mcq_markdown(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(qc, "QUESTIONS_DIR", tmp_path)
    md = """
Q. What is HCF of 8 and 12?
- 2
- *4
- 8
- 24
"""
    result = qc.import_questions(
        md,
        kind="mcq",
        topic_id="mcq.loop.hcf",
        note_topic_ids=["MT1-T02"],
    )
    assert result["imported"] == 1
    items = qc.list_questions(tag="MT1-T02", kind="mcq")
    assert items[0]["answer_index"] == 1
    # Idempotent: second import must not duplicate
    again = qc.import_questions(
        md,
        kind="mcq",
        topic_id="mcq.loop.hcf",
        note_topic_ids=["MT1-T02"],
    )
    assert again["imported"] + again.get("updated", 0) >= 1
    assert len(qc.list_questions(tag="MT1-T02", kind="mcq")) == 1
    user_pack = tmp_path / "mcq" / "_user" / "mcq.loop.hcf.json"
    assert user_pack.is_file()
