"""Soft daily-practice nudge helpers."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from backend.quiz.daily_practice import build_daily_practice_nudge


def test_daily_practice_nudge_from_next_step():
    db = MagicMock()
    with patch(
        "backend.quiz.next_step.compute_next_step",
        return_value={
            "action": "review_due",
            "label": "Review 5 due",
            "to": "/review?tab=due",
            "reason": "Protect retention",
            "due_count": 5,
        },
    ):
        out = build_daily_practice_nudge(db, user_id=1)
    assert out["show"] is True
    assert out["due_count"] == 5
    assert out["to"] == "/review?tab=due"
    assert "5" in out["label"]
    assert out["action"] == "review_due"


def test_daily_practice_dialogue_pool():
    from backend.behavior.voice_agent import dialogues

    dialogues.reset_for_tests()
    assert "daily_practice_nudge" in dialogues.all_categories()
    line = dialogues.pick("daily_practice_nudge", due="7")
    assert "7" in line
