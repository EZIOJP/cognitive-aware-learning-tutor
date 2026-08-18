"""Lecture-note quiz generation must stay notes-first and seed the shared quiz deck."""

from unittest.mock import MagicMock


def test_library_quiz_generation_prefers_notes_and_seeds_study_deck(monkeypatch):
    from backend.transcripts import router
    from backend.transcripts.router import GenerateIntelRequest

    captured: dict[str, object] = {}
    questions = [
        {
            "id": "note-q1",
            "question": "What does vectorization avoid?",
            "options": ["Python loops", "Arrays", "Indexes", "Data"],
            "answer_index": 0,
        }
    ]
    monkeypatch.setattr(router, "_load_sources", lambda *args: ["## Vectorization\nAvoid Python loops."])
    monkeypatch.setattr(
        "backend.quiz.review_cards.weak_concepts_for_retrieval",
        lambda *args: [],
    )
    monkeypatch.setattr(
        router,
        "generate_quiz_items",
        lambda texts, **kwargs: captured.update({"texts": texts, **kwargs})
        or {"questions": questions, "topics_covered": ["vectorization"]},
    )
    monkeypatch.setattr(router, "quiz_to_markdown", lambda *_args, **_kwargs: "# Quiz")
    monkeypatch.setattr(router, "create_note_file", lambda *args, **kwargs: object())
    monkeypatch.setattr(router, "note_storage_path", lambda _row: "lecture/quiz.md")

    from backend.quiz import handler

    monkeypatch.setattr(
        handler,
        "save_deck",
        lambda *_args, **kwargs: captured.update({"deck": kwargs}) or {"id": 7, "cards_seeded": 1},
    )

    body = GenerateIntelRequest(source_paths=["lecture/notes.md"], topic="Vectorization")
    user = MagicMock(id=1)
    result = router.post_generate_quiz(body, db=MagicMock(), user=user)

    assert captured["prefer_notes"] is True
    assert captured["deck"]["domain"] == "study"
    assert result["deck_id"] == 7
    assert result["cards_seeded"] == 1
