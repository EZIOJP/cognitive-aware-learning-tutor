"""Layer-0 skill catalog + generators + aptitude ladder."""

from unittest.mock import MagicMock

from backend.math.generators.layer0 import (
    generate_for_node,
    parse_factors_from_prompt,
    times_strategy_hint,
)
from backend.math.skills import generate_drill_items, get_node, list_nodes, node_status, reload_catalog


def setup_function():
    reload_catalog()


def test_layer0_catalog_has_root_unlocked_structure():
    nodes = list_nodes()
    assert any(n["id"] == "times_1_20" for n in nodes)
    root = get_node("times_1_20")
    assert root is not None
    assert root["prereqs"] == []
    stretch = get_node("times_21_50")
    assert stretch is not None
    assert "times_1_20" in stretch["prereqs"]
    assert get_node("squares_upto_50") is not None
    assert get_node("powers_8_important") is not None


def test_core_times_excludes_trivial_factors():
    node = get_node("times_1_20")
    assert node
    for _ in range(40):
        p = generate_for_node(node)
        factors = p.get("factors") or parse_factors_from_prompt(p["prompt"])
        assert factors
        assert 1 not in factors
        assert 2 not in factors
        assert 10 not in factors
        assert "×" in p["prompt"]
        assert p["explanation"]  # strategy hint always present


def test_generate_times_tables_uses_sympy_product():
    node = get_node("times_1_20")
    assert node
    p = generate_for_node(node)
    assert p["source"] == "skill_generator"
    assert "×" in p["prompt"]
    assert p["expected_answer"].lstrip("-").isdigit()


def test_squares_and_powers_ranges():
    sq = get_node("squares_upto_50")
    assert sq
    for _ in range(20):
        p = generate_for_node(sq)
        assert "²" in p["prompt"] or "^2" in p["prompt"]
        base = (p.get("factors") or [0])[0]
        assert 2 <= base <= 50

    p8 = get_node("powers_8_important")
    assert p8
    for _ in range(15):
        p = generate_for_node(p8)
        base = (p.get("factors") or [0])[0]
        assert base in (2, 3, 5, 10)


def test_strategy_hint_near_ten():
    hint = times_strategy_hint(19, 6)
    assert "20" in hint or "Near" in hint


def test_parse_factors_from_prompt():
    assert parse_factors_from_prompt("What is 12 × 13?") == [12, 13]
    assert parse_factors_from_prompt("What is 7²?") == [7]
    assert parse_factors_from_prompt("What number × 8 = 56?") == [8]


def test_generate_drill_items_sets_topic_to_skill_id():
    items = generate_drill_items("times_1_20", 3)
    assert len(items) == 3
    assert all(it["topic"] == "times_1_20" for it in items)
    assert all(it["kind"] == "math" for it in items)
    assert all(it.get("hint") for it in items)


def test_daily_mixed_builds_varied_pack():
    items = generate_drill_items("daily_mixed_5", 5)
    assert len(items) == 5
    prompts = [i["prompt"] for i in items]
    assert len(set(prompts)) >= 3


def test_node_status_locked_until_prereq():
    db = MagicMock()
    db.query.return_value.filter.return_value.order_by.return_value.limit.return_value.all.return_value = []
    # KgNode path for speed also uses query().filter().first()
    db.query.return_value.filter.return_value.first.return_value = None
    root = get_node("times_1_20")
    stretch = get_node("times_21_50")
    cubes = get_node("cubes_upto_20")
    assert root and stretch and cubes
    assert node_status(db, user_id=1, node=root) == "available"
    assert node_status(db, user_id=1, node=stretch) == "locked"
    assert node_status(db, user_id=1, node=cubes) == "locked"
