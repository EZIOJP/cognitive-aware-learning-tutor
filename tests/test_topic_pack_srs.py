"""Topic-indexed lecture quiz cards for spaced repetition."""

from types import SimpleNamespace

from backend.quiz.review_cards import (
    expand_cards_to_quiz_items,
    group_items_into_topic_packs,
)


def test_group_items_into_topic_packs_preserves_order():
    items = [
        {"id": "a", "topic_id": "L5-T02", "question": "Q2", "concept": "Indexing"},
        {"id": "b", "topic_id": "L5-T01", "question": "Q1", "concept": "Memory"},
        {"id": "c", "topic_id": "L5-T02", "question": "Q2b", "concept": "Indexing"},
        {"id": "d", "question": "untagged"},
    ]
    packs = group_items_into_topic_packs(items)
    assert [p["topic_id"] for p in packs] == ["L5-T02", "L5-T01"]
    assert len(packs[0]["questions"]) == 2
    assert len(packs[1]["questions"]) == 1


def test_expand_topic_pack_card_into_questions():
    pack = {
        "kind": "topic_pack",
        "topic_id": "L5-T01",
        "questions": [
            {"id": "q1", "question": "Why memory?", "options": ["A", "B"], "answer_index": 0},
            {"id": "q2", "question": "What is contiguous?", "options": ["A", "B"], "answer_index": 1},
        ],
    }
    card = SimpleNamespace(
        id=9,
        payload_json=__import__("json").dumps(pack),
        topic="L5-T01",
        note_path="data_foundations/lecture_5/notes.md",
        domain="study",
        format="mcq",
        item_key="study:topic-L5-T01",
        label="L5-T01 — Memory",
    )
    items = expand_cards_to_quiz_items([card])
    assert len(items) == 2
    assert items[0]["schedule_topic_pack"] is True
    assert items[0]["pack_index"] == 0
    assert items[1]["pack_size"] == 2
    assert items[0]["review_card_id"] == 9
