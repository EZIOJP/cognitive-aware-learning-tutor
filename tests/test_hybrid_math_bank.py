"""Hybrid math bank: curated content_bank + mathgenerator on-demand indexing."""

from __future__ import annotations

from backend.core.auth import get_current_user
from backend.db.session import SessionLocal
from backend.main import app
from backend.models import MathQuestion, User
from backend.quiz import math_generators as mg
from backend.quiz.handler import start_session
from fastapi.testclient import TestClient


def test_list_generator_recipes():
    recipes = mg.list_recipes(refresh=True)
    assert len(recipes) >= 100
    assert all(r.note_topic_id.startswith("MT") for r in recipes)
    assert mg.recipe_by_topic_id(recipes[0].topic_id) is not None


def test_generate_and_index_into_math_questions():
    recipes = mg.list_recipes(refresh=True)
    # Prefer a simple arithmetic generator
    recipe = next((r for r in recipes if r.gen_id == 0), recipes[0])
    db = SessionLocal()
    try:
        before = db.query(MathQuestion).filter(MathQuestion.source == "mathgenerator").count()
        items = mg.generate_quiz_items(db, recipe=recipe, count=3)
        assert len(items) == 3
        assert all(i.get("expected_answer") for i in items)
        after = db.query(MathQuestion).filter(MathQuestion.source == "mathgenerator").count()
        assert after >= before + 1
    finally:
        db.close()


def test_start_session_use_generator():
    db = SessionLocal()
    try:
        user = db.query(User).first()
        assert user is not None
        out = start_session(
            db,
            user=user,
            domain="math",
            config={"use_generator": True, "note_topic_id": "MT1-T01", "count": 2},
        )
        assert out["session_id"]
        assert out["question"].get("prompt")
    finally:
        db.close()


def test_hybrid_catalog_route():
    user = User(id=1, username="test", password_hash="hash")

    def _user():
        return user

    app.dependency_overrides[get_current_user] = _user
    try:
        client = TestClient(app)
        r = client.get("/api/quiz/content/catalog?kind=math")
        assert r.status_code == 200
        body = r.json()
        assert body.get("hybrid") is True
        assert body.get("generator_count", 0) >= 100
        assert body.get("topic_count", 0) >= 40
    finally:
        app.dependency_overrides.pop(get_current_user, None)
