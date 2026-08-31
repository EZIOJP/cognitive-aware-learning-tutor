"""Exit PIN for desktop tracker stop/restart."""

from backend.behavior.tracker_exit import (
    exit_confirmation_required,
    exit_prompt_hint,
    exit_secret_accepted,
    expected_exit_secret,
    normalize_exit_input,
)


def test_no_pin_skips_confirmation(monkeypatch):
    monkeypatch.delenv("TRACKER_EXIT_PIN", raising=False)
    assert not exit_confirmation_required()
    assert expected_exit_secret() == ""
    assert exit_secret_accepted(None)
    assert exit_secret_accepted("")
    assert exit_secret_accepted("anything")
    assert "Confirm" in exit_prompt_hint()


def test_custom_pin(monkeypatch):
    monkeypatch.setenv("TRACKER_EXIT_PIN", "48291")
    assert exit_confirmation_required()
    assert expected_exit_secret() == "48291"
    assert exit_secret_accepted("48291")
    assert not exit_secret_accepted("I AM DONE TRACKING")
    assert not exit_secret_accepted("")
    assert not exit_secret_accepted(None)
    assert "TRACKER_EXIT_PIN" in exit_prompt_hint()


def test_normalize_collapses_whitespace():
    assert normalize_exit_input("  a   b  ") == "a b"


def test_cli_skips_prompt_without_pin(monkeypatch):
    from backend.behavior.tracker_exit import prompt_exit_secret_cli

    monkeypatch.delenv("TRACKER_EXIT_PIN", raising=False)

    def _fail_input(_p=""):
        raise AssertionError("input should not be called when PIN unset")

    monkeypatch.setattr("builtins.input", _fail_input)
    assert prompt_exit_secret_cli(reason="stop") is True


def test_cli_prompt_accepts_pin(monkeypatch, capsys):
    from backend.behavior.tracker_exit import prompt_exit_secret_cli

    monkeypatch.setenv("TRACKER_EXIT_PIN", "9911")
    monkeypatch.setattr("builtins.input", lambda _p="": "9911")
    assert prompt_exit_secret_cli(reason="stop") is True
    out = capsys.readouterr().out
    assert "OK" in out


def test_cli_prompt_rejects_wrong(monkeypatch):
    from backend.behavior.tracker_exit import prompt_exit_secret_cli

    monkeypatch.setenv("TRACKER_EXIT_PIN", "9911")
    monkeypatch.setattr("builtins.input", lambda _p="": "nope")
    assert prompt_exit_secret_cli(reason="stop") is False
