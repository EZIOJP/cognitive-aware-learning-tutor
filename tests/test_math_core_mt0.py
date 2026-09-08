from backend.quiz.math_core import (
    MATH_CORE_READ_TAGS,
    canonical_tag,
    label_for_tag,
    learn_order,
)


def test_mt0_basics_before_powers():
    assert learn_order("MT0-T01") < learn_order("MT0-T04")
    assert learn_order("MT0-T04") < learn_order("MT0-T05")
    assert learn_order("MT0-T01") < learn_order("MT1-T02")


def test_legacy_aliases_map_to_mt0():
    assert canonical_tag("MT1-T19") == "MT0-T01"
    assert canonical_tag("MT1-T17") == "MT0-T05"
    assert learn_order("MT1-T19") == learn_order("MT0-T01")


def test_read_tags_basics_first():
    assert MATH_CORE_READ_TAGS[0] == "MT1-T01"
    assert MATH_CORE_READ_TAGS[1] == "MT0-T01"
    assert "MT0-T09" in MATH_CORE_READ_TAGS
    assert label_for_tag("MT0-T01").lower().startswith("math core")
