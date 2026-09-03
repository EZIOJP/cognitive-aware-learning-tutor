from backend.math.curriculum_pass.curriculum import (
    build_reverse_index,
    normalize_topic_id,
)


def test_normalize_topic_id_trim_lower():
    assert normalize_topic_id("  Math.Aptitude.Sat-Algebra ") == "math.aptitude.sat-algebra"


def test_reverse_index_maps_prefer_to_mt():
    cur = {
        "levels": [
            {
                "steps": [
                    {
                        "note_topic_id": "MT1-T05",
                        "title": "Averages",
                        "prefer_topic_ids": ["math.aptitude.sat-data"],
                    },
                    {
                        "note_topic_id": "MT1-T07",
                        "title": "Time & work",
                        "prefer_topic_ids": [
                            "math.aptitude.sat-data",
                            "math.aptitude.gen-time-work",
                        ],
                    },
                ]
            }
        ]
    }
    idx = build_reverse_index(cur)
    assert idx[normalize_topic_id("math.aptitude.sat-data")] == {"MT1-T05", "MT1-T07"}
    assert idx[normalize_topic_id("math.aptitude.gen-time-work")] == {"MT1-T07"}
