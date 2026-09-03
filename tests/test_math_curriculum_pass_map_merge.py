from backend.math.curriculum_pass.curriculum import normalize_topic_id
from backend.math.curriculum_pass.map_packs import map_pack
from backend.math.curriculum_pass.merge import merge_question


def test_merge_fill_empty_only():
    existing = {
        "id": "math.mathqa.1",
        "source": "mathqa",
        "source_id": "1",
        "answer": "42",
        "hint": "",
        "tags": ["old"],
    }
    incoming = {
        "id": "math.mathqa.1",
        "source": "mathqa",
        "source_id": "1",
        "answer": "99",
        "hint": "use algebra",
        "tags": ["new"],
    }
    out = merge_question(existing, incoming)
    assert out["answer"] == "42"
    assert out["hint"] == "use algebra"


def test_map_pack_additive_lockstep_and_multi():
    reverse = {
        normalize_topic_id("math.aptitude.sat-data"): {"MT1-T05", "MT1-T07"},
    }
    pack = {
        "topic": {
            "topic_id": "math.aptitude.sat-data",
            "note_topic_ids": ["MT1-T05", "L9-T01"],
            "title": "SAT data",
        },
        "questions": [
            {
                "id": "math.sat.1",
                "source": "sat",
                "source_id": "1",
                "problem": "x",
                "tags": ["MT1-T05"],
            },
        ],
    }
    result = map_pack(pack, reverse, curriculum_mts={"MT1-T05", "MT1-T07"})
    assert result.status == "mapped"
    assert result.multi_topic is True
    assert set(result.pack["topic"]["note_topic_ids"]) == {"MT1-T05", "MT1-T07"}
    assert "L9-T01" in result.removed_note_topic_ids
    assert set(result.pack["questions"][0]["tags"]) >= {"MT1-T05", "MT1-T07"}


def test_quarantine_when_not_in_index():
    pack = {
        "topic": {"topic_id": "math.orphan.pack", "note_topic_ids": [], "title": "x"},
        "questions": [],
    }
    result = map_pack(pack, {}, curriculum_mts=set())
    assert result.status == "quarantined"
