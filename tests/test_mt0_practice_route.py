"""MT0 worksheet focus uses on-demand Math Core drills (not silent MT1-T01 remap)."""

from backend.quiz.math_core_drills import generate_drill_items, supports_worksheet_drills
from backend.quiz.study_loop import resolve_practice_route


def test_mt0_worksheet_routes_to_own_drills():
    route = resolve_practice_route("MT0-T01", count=20)
    assert route.domain == "math"
    assert route.config.get("note_topic_id") == "MT0-T01"
    assert route.config.get("math_core_drill") is True


def test_legacy_worksheet_canonicalizes_to_mt0():
    route = resolve_practice_route("MT1-T19", count=20)
    assert route.config.get("note_topic_id") == "MT0-T01"
    assert route.config.get("math_core_drill") is True


def test_generate_tables_coverage_bias():
    assert supports_worksheet_drills("MT0-T04")
    items = generate_drill_items(tag="MT0-T04", count=10, user_id=1)
    assert len(items) == 10
    assert all(it.get("note_topic_ids") == ["MT0-T04"] for it in items)
    assert all("²" in it["prompt"] or "^" in it["prompt"] or "{2}" in it["prompt"] for it in items)


def test_chunk_and_coverage_on_correct_only(tmp_path, monkeypatch):
    from backend.quiz import math_core_drills as mcd

    path = tmp_path / "cov.json"
    monkeypatch.setattr(mcd, "_COVERAGE_PATH", path)
    items = mcd.generate_drill_items(tag="MT0-T04", count=5, user_id=42)
    assert len(items) == 5
    assert mcd.practiced_keys(42, "MT0-T04") == set()
    key = items[0]["fact_key"]
    mcd.mark_practiced(42, "MT0-T04", [key])
    stats = mcd.coverage_stats(42, "MT0-T04")
    assert stats["practiced"] == 1
    assert stats["total"] == 50
    assert mcd.can_keep_going(42, "MT0-T04") is True


def test_diversify_tables_spreads_factors():
    from backend.quiz import math_core_drills as mcd

    items = mcd.generate_drill_items(tag="MT0-T01", count=12, user_id=None)
    left = set()
    for it in items:
        parts = mcd._mul_parts(it["fact_key"])
        assert parts
        left.add(parts[0])
    assert len(left) >= 4
