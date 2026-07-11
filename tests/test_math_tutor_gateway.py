"""Math tutor hints — gateway text path + hybrid vision branch."""

from __future__ import annotations

from unittest.mock import patch

from backend.math.ollama_tutor import generate_tutor_hint


def test_text_hint_uses_gateway_task_and_timeout():
    captured: dict = {}

    def fake_generate(prompt, **kwargs):
        captured.update(kwargs)
        return '{"hint":"Try isolating x.","question":"What operation clears the constant?","detected_concept":"algebra"}'

    with patch("backend.math.ollama_tutor.llm_reachable", return_value=True):
        with patch("backend.math.ollama_tutor.ollama_generate", side_effect=fake_generate):
            result = generate_tutor_hint(
                prompt="Solve 2x + 4 = 10",
                topic="algebra",
                gamma=40,
                attention=60,
                canvas_image="",
            )

    assert result is not None
    assert result["hint"] == "Try isolating x."
    assert captured.get("task") == "math_hint"
    assert captured.get("timeout") == 45.0
    assert captured.get("tier") is None


def test_text_hint_passes_llm_tier():
    captured: dict = {}

    def fake_generate(prompt, **kwargs):
        captured.update(kwargs)
        return '{"hint":"Check signs.","question":"Did you distribute correctly?","detected_concept":"algebra"}'

    with patch("backend.math.ollama_tutor.llm_reachable", return_value=True):
        with patch("backend.math.ollama_tutor.ollama_generate", side_effect=fake_generate):
            generate_tutor_hint(
                prompt="Expand (x+2)(x-3)",
                topic="algebra",
                gamma=30,
                attention=70,
                canvas_image="",
                llm_tier="medium",
            )

    assert captured.get("tier") == "medium"


def test_vision_path_skips_gateway_when_vision_model_set(monkeypatch):
    monkeypatch.setenv("OLLAMA_VISION_MODEL", "llava:7b")
    monkeypatch.setenv("OLLAMA_URL", "http://127.0.0.1:11434")

    vision_result = {
        "hint": "Look at the coefficient.",
        "question": "What do you multiply both sides by?",
        "detected_concept": "fractions",
    }

    with patch("backend.math.ollama_tutor.ollama_vision_url", return_value="http://127.0.0.1:11434"):
        with patch("backend.math.ollama_tutor._vision_hint_via_ollama", return_value=vision_result) as vision_mock:
            with patch("backend.math.ollama_tutor.ollama_generate") as gateway_mock:
                result = generate_tutor_hint(
                    prompt="1/2 x = 4",
                    topic="fractions",
                    gamma=30,
                    attention=70,
                    canvas_image="data:image/png;base64," + ("A" * 120),
                )

    gateway_mock.assert_not_called()
    vision_mock.assert_called_once()
    assert result == vision_result


def test_returns_none_when_llm_unreachable():
    with patch("backend.math.ollama_tutor.llm_reachable", return_value=False):
        result = generate_tutor_hint(
            prompt="x^2 = 9",
            topic="algebra",
            gamma=30,
            attention=70,
            canvas_image="",
        )
    assert result is None
