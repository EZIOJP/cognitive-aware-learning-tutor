"""Adaptive aptitude mathgenerator + corrected name→MT mappings."""

from __future__ import annotations

from backend.quiz import math_generators as mg


def test_percentage_and_profit_mappings_are_correct():
    recipes = {r.name: r for r in mg.list_recipes(refresh=True)}
    assert recipes["percentage"].gen_id == 80
    assert recipes["percentage"].note_topic_id == "MT1-T03"
    assert recipes["profit_loss_percent"].gen_id == 63
    assert recipes["profit_loss_percent"].note_topic_id == "MT1-T08"
    assert recipes["vector_dot"].gen_id == 72
    assert recipes["vector_dot"].note_topic_id == "MT3-T01"
    assert recipes["compound_interest"].gen_id == 78
    assert recipes["arithmetic_progression_term"].gen_id == 82


def test_aptitude_core_recipes_exist():
    core = mg.aptitude_recipes()
    assert len(core) >= 40
    assert all(r.aptitude_core for r in core)
    assert "MT1-T03" in {r.note_topic_id for r in core}


def test_generate_percentage_looks_like_percent():
    from backend.db.session import SessionLocal

    recipes = {r.name: r for r in mg.list_recipes(refresh=True)}
    r = recipes["percentage"]
    db = SessionLocal()
    try:
        items = mg.generate_quiz_items(db, recipe=r, count=2)
        assert len(items) == 2
        assert items[0]["gen_id"] == 80
        joined = " ".join(i["prompt"].lower() for i in items)
        assert "%" in joined or "percent" in joined or "100" in joined
    finally:
        db.close()


def test_adaptive_aptitude_generates():
    from backend.db.session import SessionLocal
    from backend.models import User

    db = SessionLocal()
    try:
        user = db.query(User).first()
        assert user is not None
        items = mg.generate_quiz_items(
            db,
            count=5,
            adaptive=True,
            aptitude_only=True,
            user_id=user.id,
        )
        assert len(items) == 5
        assert all(i.get("repeat_until_correct") for i in items)
        assert all(i.get("gen_id") is not None for i in items)
    finally:
        db.close()
