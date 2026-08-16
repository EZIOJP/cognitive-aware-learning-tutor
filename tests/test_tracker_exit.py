"""Exit PIN / confirm phrase for desktop tracker tray."""

from backend.behavior.tracker_exit import (
    DEFAULT_EXIT_PHRASE,
    exit_prompt_hint,
    exit_secret_accepted,
    expected_exit_secret,
    normalize_exit_input,
)


def test_default_phrase_accepted(monkeypatch):
    monkeypatch.delenv("TRACKER_EXIT_PIN", raising=False)
    assert expected_exit_secret() == DEFAULT_EXIT_PHRASE
    assert exit_secret_accepted("I AM DONE TRACKING")
    assert exit_secret_accepted("  i am done tracking  ")
    assert not exit_secret_accepted("quit")
    assert not exit_secret_accepted("")
    assert not exit_secret_accepted(None)


def test_custom_pin(monkeypatch):
    monkeypatch.setenv("TRACKER_EXIT_PIN", "48291")
    assert expected_exit_secret() == "48291"
    assert exit_secret_accepted("48291")
    assert not exit_secret_accepted(DEFAULT_EXIT_PHRASE)
    assert "TRACKER_EXIT_PIN" in exit_prompt_hint()


def test_normalize_collapses_whitespace():
    assert normalize_exit_input("  a   b  ") == "a b"


def test_cli_prompt_accepts_pin(monkeypatch, capsys):
    from backend.behavior.tracker_exit import prompt_exit_secret_cli

    monkeypatch.setenv("TRACKER_EXIT_PIN", "9911")
    monkeypatch.setattr("builtins.input", lambda _p="": "9911")
    assert prompt_exit_secret_cli(reason="stop") is True
    out = capsys.readouterr().out
    assert "OK" in out


def test_cli_prompt_rejects_wrong(monkeypatch):
    from backend.behavior.tracker_exit import prompt_exit_secret_cli

    monkeypatch.delenv("TRACKER_EXIT_PIN", raising=False)
    monkeypatch.setattr("builtins.input", lambda _p="": "nope")
    assert prompt_exit_secret_cli(reason="stop") is False
