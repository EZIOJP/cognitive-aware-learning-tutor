"""Per-topic difficulty ladder: classify, filter, unlock."""

from __future__ import annotations

from pathlib import Path

from backend.quiz import topic_level as tl


def test_classify_olympiad_and_competition():
    assert tl.classify_item({"topic_id": "math.olympiad.mathnet-number", "difficulty": "easy"}) == "advanced"
    assert tl.classify_item({"topic_id": "math.competition.number-theory", "difficulty": "easy"}) == "hard"
    assert tl.classify_item({"topic_id": "math.aptitude.dm-add-sub", "difficulty": "easy"}) == "easy"
    assert tl.classify_item({"topic_id": "math.aptitude.sat-algebra", "difficulty": "medium"}) == "medium"
    assert tl.classify_item({"topic_id": "math.gen.foo", "difficulty": ""}) == "easy"


def test_filter_items_for_level():
    items = [
        {"id": "1", "topic_id": "math.aptitude.dm-mul", "difficulty": "easy"},
        {"id": "2", "topic_id": "math.competition.prealgebra", "difficulty": "hard"},
        {"id": "3", "topic_id": "math.olympiad.mathnet-number", "difficulty": "hard"},
    ]
    easy = tl.filter_items_for_level(items, "easy")
    assert [x["id"] for x in easy] == ["1"]
    hard = tl.filter_items_for_level(items, "hard")
    assert [x["id"] for x in hard] == ["2"]
    adv = tl.filter_items_for_level(items, "advanced")
    assert [x["id"] for x in adv] == ["3"]


def test_advance_requires_pass_accuracy(tmp_path: Path):
    path = tmp_path / "topic_difficulty.json"
    assert tl.get_stored_level(1, "MT1-T07", path=path) == "easy"
    no = tl.consider_advance(1, "MT1-T07", correct=7, total=10, path=path)
    assert no["advanced"] is False
    assert tl.get_stored_level(1, "MT1-T07", path=path) == "easy"

    # Force inventory so unlock isn't skipped for empty rungs.
    def fake_levels(_tag: str) -> list[str]:
        return ["easy", "medium", "hard", "advanced"]

    import backend.quiz.topic_level as mod

    original = mod.levels_with_inventory
    mod.levels_with_inventory = fake_levels  # type: ignore[assignment]
    try:
        yes = tl.consider_advance(1, "MT1-T07", correct=8, total=10, path=path)
        assert yes["advanced"] is True
        assert yes["next_level"] == "medium"
        assert tl.get_stored_level(1, "MT1-T07", path=path) == "medium"
    finally:
        mod.levels_with_inventory = original  # type: ignore[assignment]


def test_curriculum_prefer_mt1_t01():
    prefs = tl.curriculum_prefer_ids("MT1-T01", level="easy")
    assert "math.aptitude.dm-add-sub" in prefs
    assert all("olympiad" not in p for p in prefs)
    assert all("competition" not in p for p in prefs)
    stretch = tl.curriculum_prefer_ids("MT1-T01", level="advanced")
    assert any("olympiad" in p or "competition" in p for p in stretch)


def test_allow_generators_easy_only():
    assert tl.allow_generators("easy") is True
    assert tl.allow_generators("medium") is False
    assert tl.allow_generators("hard") is False
