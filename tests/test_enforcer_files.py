"""Tests for enforcer_policy strong locks + browser labels Tier 1."""

from __future__ import annotations

import time

import pytest

from backend.behavior.browser_labels import browser_display_name
from backend.behavior.enforcer_files import EnforcerLockError, write_policy_file, read_policy_file


@pytest.fixture()
def policy_paths(tmp_path, monkeypatch):
    import backend.behavior.enforcer_files as ef
    import backend.behavior.uninstall_protect as up

    monkeypatch.setattr(ef, "BEHAVIOR_DIR", tmp_path)
    monkeypatch.setattr(ef, "POLICY_PATH", tmp_path / "enforcer_policy.json")
    monkeypatch.setattr(up, "apply_protect_uninstall", lambda **kw: {"ok": True, "skipped": True})
    monkeypatch.setattr(up, "write_protect_state_file", lambda p: None)
    return tmp_path


def test_browser_display_broad(policy_paths):
    assert browser_display_name("brave.exe") == "Brave"
    assert browser_display_name("vivaldi.exe") == "Vivaldi"
    assert browser_display_name("librewolf.exe") == "LibreWolf"
    assert browser_display_name("opera.exe") == "Opera"
    assert browser_display_name("chrome.exe") == "Google Chrome"
    assert browser_display_name("arc.exe") == "Arc"
    assert browser_display_name("duckduckgo.exe") == "DuckDuckGo"


def test_write_read_policy(policy_paths):
    out = write_policy_file(
        hard_block_armed=True,
        gate_locked=True,
        incubation_active=False,
        exes=["Notepad.EXE", "steam.exe", "steam.exe"],
        note="test",
    )
    assert out["hard_block_armed"] is True
    assert out["exes"] == ["notepad.exe", "steam.exe"]
    got = read_policy_file()
    assert got is not None
    assert got["exes"] == ["notepad.exe", "steam.exe"]
    assert got["lock_mode"] == "none"
    assert got["anti_tamper"] is True


def test_password_lock_blocks_disarm(policy_paths):
    write_policy_file(
        hard_block_armed=True,
        gate_locked=True,
        lock_mode="password",
        unlock_password="secret",
        exes=["notepad.exe"],
    )
    with pytest.raises(EnforcerLockError):
        write_policy_file(
            hard_block_armed=False,
            gate_locked=False,
            provided_unlock="wrong",
        )
    write_policy_file(
        hard_block_armed=False,
        gate_locked=False,
        provided_unlock="secret",
    )
    got = read_policy_file()
    assert got["hard_block_armed"] is False
    assert got["lock_mode"] == "none"


def test_timer_lock_blocks_until_expiry(policy_paths):
    until = int(time.time()) + 3600
    write_policy_file(
        hard_block_armed=True,
        gate_locked=True,
        lock_mode="timer",
        lock_until_unix=until,
        exes=["notepad.exe"],
    )
    with pytest.raises(EnforcerLockError):
        write_policy_file(hard_block_armed=False, gate_locked=False)
    # Expired timer allows disarm
    write_policy_file(
        hard_block_armed=True,
        gate_locked=True,
        lock_mode="timer",
        lock_until_unix=int(time.time()) - 5,
        exes=["notepad.exe"],
    )
    write_policy_file(hard_block_armed=False, gate_locked=False)
    assert read_policy_file()["hard_block_armed"] is False


def test_kill_list_locked_while_armed_password(policy_paths):
    write_policy_file(
        hard_block_armed=True,
        gate_locked=True,
        lock_mode="password",
        unlock_password="secret",
        exes=["steam.exe"],
    )
    with pytest.raises(EnforcerLockError, match="Kill list locked"):
        write_policy_file(
            hard_block_armed=True,
            gate_locked=True,
            lock_mode="password",
            unlock_password="secret",
            exes=["notepad.exe"],  # try remove steam without unlock
        )
    # Same list OK
    write_policy_file(
        hard_block_armed=True,
        gate_locked=True,
        lock_mode="password",
        unlock_password="secret",
        exes=["steam.exe"],
    )
    # Unlock allows list change
    write_policy_file(
        hard_block_armed=True,
        gate_locked=True,
        lock_mode="password",
        unlock_password="secret",
        provided_unlock="secret",
        exes=["notepad.exe"],
    )
    assert read_policy_file()["exes"] == ["notepad.exe"]


def test_protect_uninstall_requires_secret(policy_paths, monkeypatch):
    import backend.behavior.uninstall_protect as up

    monkeypatch.setattr(up, "apply_protect_uninstall", lambda **kw: {"ok": True})
    monkeypatch.setattr(up, "write_protect_state_file", lambda p: None)

    with pytest.raises(EnforcerLockError, match="password or phrase"):
        write_policy_file(
            hard_block_armed=False,
            gate_locked=False,
            protect_uninstall=True,
        )


def test_protect_uninstall_on_off(policy_paths, monkeypatch):
    import backend.behavior.uninstall_protect as up

    calls: list[bool] = []
    monkeypatch.setattr(
        up, "apply_protect_uninstall", lambda **kw: calls.append(bool(kw.get("protect"))) or {"ok": True}
    )
    monkeypatch.setattr(up, "write_protect_state_file", lambda p: None)

    write_policy_file(
        hard_block_armed=False,
        gate_locked=False,
        protect_uninstall=True,
        unlock_password="gate",
    )
    got = read_policy_file()
    assert got["protect_uninstall"] is True
    assert got["unlock_password"] == "gate"
    assert calls == [True]

    with pytest.raises(EnforcerLockError, match="Uninstall protected"):
        write_policy_file(
            hard_block_armed=False,
            gate_locked=False,
            protect_uninstall=False,
            provided_unlock="wrong",
        )

    write_policy_file(
        hard_block_armed=False,
        gate_locked=False,
        protect_uninstall=False,
        provided_unlock="gate",
    )
    assert read_policy_file()["protect_uninstall"] is False
    assert calls[-1] is False


def test_disarm_keeps_secrets_when_protect_on(policy_paths, monkeypatch):
    import backend.behavior.uninstall_protect as up

    monkeypatch.setattr(up, "apply_protect_uninstall", lambda **kw: {"ok": True})
    monkeypatch.setattr(up, "write_protect_state_file", lambda p: None)

    write_policy_file(
        hard_block_armed=True,
        gate_locked=True,
        lock_mode="password",
        unlock_password="secret",
        protect_uninstall=True,
        exes=["notepad.exe"],
    )
    write_policy_file(
        hard_block_armed=False,
        gate_locked=False,
        provided_unlock="secret",
    )
    got = read_policy_file()
    assert got["hard_block_armed"] is False
    assert got["protect_uninstall"] is True
    assert got["unlock_password"] == "secret"
