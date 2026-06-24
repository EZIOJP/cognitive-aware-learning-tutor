from unittest.mock import MagicMock, patch

from backend.core import ollama_client
from backend.core.ollama_client import LlmOptions


@patch("backend.core.ollama_client._settings")
def test_lmstudio_native_uses_v1_chat(mock_settings):
    settings = MagicMock()
    settings.ollama_enabled = True
    settings.llm_provider = "lmstudio"
    settings.ollama_url = "http://127.0.0.1:1234"
    settings.ollama_model = "google/gemma-4-e4b"
    settings.llm_max_tokens = 8192
    settings.llm_api_key = "lm-studio"
    mock_settings.return_value = settings

    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = {
        "output": [{"type": "message", "content": "## Topic\n\n- point one"}],
    }

    mock_client = MagicMock()
    mock_client.__enter__ = MagicMock(return_value=mock_client)
    mock_client.__exit__ = MagicMock(return_value=False)
    mock_client.post.return_value = mock_response

    with patch("backend.core.ollama_client.httpx.Client", return_value=mock_client):
        out = ollama_client.ollama_generate(
            "Summarize this lecture chunk.",
            llm=LlmOptions(provider="lmstudio", base_url="http://127.0.0.1:1234", model="google/gemma-4-e4b"),
        )

    assert out == "## Topic\n\n- point one"
    mock_client.post.assert_called_once()
    args, kwargs = mock_client.post.call_args
    assert args[0] == "http://127.0.0.1:1234/api/v1/chat"
    assert kwargs["json"]["model"] == "google/gemma-4-e4b"
    assert kwargs["json"]["input"] == "Summarize this lecture chunk."


@patch("backend.core.ollama_client._settings")
def test_openai_generate_uses_chat_completions(mock_settings):
    settings = MagicMock()
    settings.ollama_enabled = True
    settings.llm_provider = "openai"
    settings.ollama_url = "http://127.0.0.1:1234"
    settings.ollama_model = "google/gemma-4-e4b"
    settings.llm_max_tokens = 8192
    settings.llm_api_key = "lm-studio"
    mock_settings.return_value = settings

    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = {
        "choices": [{"message": {"content": "## Topic\n\n- point one"}}],
    }

    mock_client = MagicMock()
    mock_client.__enter__ = MagicMock(return_value=mock_client)
    mock_client.__exit__ = MagicMock(return_value=False)
    mock_client.post.return_value = mock_response

    with patch("backend.core.ollama_client.httpx.Client", return_value=mock_client):
        out = ollama_client.ollama_generate(
            "Summarize this lecture chunk.",
            llm=LlmOptions(provider="openai", base_url="http://127.0.0.1:1234", model="google/gemma-4-e4b"),
        )

    assert out == "## Topic\n\n- point one"
    args, _kwargs = mock_client.post.call_args
    assert args[0] == "http://127.0.0.1:1234/v1/chat/completions"


@patch("backend.core.ollama_client._settings")
def test_override_works_when_backend_llm_disabled(mock_settings):
    settings = MagicMock()
    settings.ollama_enabled = False
    settings.llm_provider = "ollama"
    settings.ollama_url = "http://127.0.0.1:11434"
    settings.ollama_model = "llama3"
    settings.llm_max_tokens = 8192
    settings.llm_api_key = ""
    mock_settings.return_value = settings

    override = LlmOptions(
        provider="lmstudio",
        base_url="http://127.0.0.1:1234",
        model="google/gemma-4-e4b",
    )
    assert ollama_client.ollama_available(override) == "http://127.0.0.1:1234"

    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = {
        "output": [{"type": "message", "content": "notes"}],
    }
    mock_client = MagicMock()
    mock_client.__enter__ = MagicMock(return_value=mock_client)
    mock_client.__exit__ = MagicMock(return_value=False)
    mock_client.post.return_value = mock_response

    with patch("backend.core.ollama_client.httpx.Client", return_value=mock_client):
        out = ollama_client.ollama_generate("prompt", llm=override)

    assert out == "notes"
