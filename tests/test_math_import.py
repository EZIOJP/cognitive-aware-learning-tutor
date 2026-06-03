from fastapi.testclient import TestClient

from backend.main import app

client = TestClient(app)


def test_math_practice_next_from_bank():
    r = client.get("/api/vocab/math/practice/next", params={"topic": "Algebra"})
    assert r.status_code == 200
    problem = r.json()["problem"]
    assert problem.get("source") == "question_bank"
    assert problem.get("question_id")
    assert "prompt" in problem


def test_export_group_words():
    r = client.get("/api/vocab/words/export/group/1")
    assert r.status_code in (200, 404)
    if r.status_code == 200:
        data = r.json()
        assert data["group_number"] == 1
        assert "words" in data


def test_math_import_preview():
    body = {
        "format_version": 1,
        "topic": "TestTopic",
        "questions": [{"prompt": "1+1?", "expected_answer": "2"}],
    }
    r = client.post("/api/math/questions/import/preview", json=body)
    assert r.status_code == 200
    assert r.json()["valid_count"] == 1
