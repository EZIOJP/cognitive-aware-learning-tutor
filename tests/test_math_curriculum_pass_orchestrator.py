import json
from pathlib import Path

from backend.math.curriculum_pass.orchestrator import run_pass


def test_orchestrator_map_only_fixture(tmp_path: Path):
    questions = tmp_path / "questions" / "math"
    notes = tmp_path / "notes" / "math"
    meta = questions / "_meta"
    questions.mkdir(parents=True)
    notes.mkdir(parents=True)

    curriculum = {
        "levels": [
            {
                "steps": [
                    {
                        "note_topic_id": "MT1-T05",
                        "title": "Averages & mixtures",
                        "prefer_topic_ids": ["math.aptitude.sat-data"],
                    }
                ]
            }
        ]
    }
    cur_path = tmp_path / "curriculum.json"
    cur_path.write_text(json.dumps(curriculum), encoding="utf-8")

    mapped = {
        "schema_version": 1,
        "kind": "math",
        "topic": {
            "topic_id": "math.aptitude.sat-data",
            "title": "SAT data",
            "note_topic_ids": [],
            "stage": "foundations",
            "path": ["Aptitude"],
            "track": "aptitude",
        },
        "questions": [
            {
                "id": "math.sat.1",
                "source": "sat",
                "source_id": "1",
                "problem": "Solve: 3x+5=20",
                "answer": "",
                "answer_format": "open",
                "tags": [],
            }
        ],
    }
    orphan = {
        "schema_version": 1,
        "kind": "math",
        "topic": {
            "topic_id": "math.orphan.pack",
            "title": "Orphan",
            "note_topic_ids": [],
            "stage": "foundations",
            "path": ["x"],
            "track": "aptitude",
        },
        "questions": [
            {
                "id": "math.authored.9",
                "source": "authored",
                "source_id": "9",
                "problem": "orphan q",
                "answer": "1",
                "tags": [],
            }
        ],
    }
    (questions / "sat-data.json").write_text(json.dumps(mapped), encoding="utf-8")
    (questions / "orphan.json").write_text(json.dumps(orphan), encoding="utf-8")

    summary = run_pass(
        curriculum_path=cur_path,
        questions_root=questions,
        notes_dir=notes,
        meta_dir=meta,
        skip_import=True,
        skip_seed=True,
        user_id=1,
        db=None,
    )
    assert summary["kept"] >= 1
    assert summary["quarantined_unmapped"] == 1
    assert (meta / "needs_topic.json").is_file()
    note = notes / "MT1_aptitude_interview_notes.md"
    assert note.is_file()
    assert "## `MT1-T05` — Averages & mixtures" in note.read_text(encoding="utf-8")
    rewritten = json.loads((questions / "sat-data.json").read_text(encoding="utf-8"))
    assert "MT1-T05" in rewritten["topic"]["note_topic_ids"]
