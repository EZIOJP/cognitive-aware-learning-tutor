"""Open / no-answer math items are valid content."""

from backend.quiz.content_schemas import MathQuestion


def test_math_question_allows_empty_answer():
    q = MathQuestion(id="t.q1", problem="Prove that…")
    assert q.answer == ""
    assert q.answer_format == "open"


def test_content_bank_loads_open_mathnet():
    from backend.quiz.content_bank import load_catalog

    c = load_catalog(refresh=True)
    open_n = sum(
        1
        for t in c.topics
        for i in t.items
        if not (i.get("expected_answer") or "").strip() or i.get("answer_format") == "open"
    )
    assert open_n >= 100, open_n
