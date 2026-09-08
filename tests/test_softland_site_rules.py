"""Tests for SoftLand site rules merge + persistence (Phase 2 → softland_policy.json)."""

from __future__ import annotations

from backend.behavior.softland_site_rules import (
    load_site_rules,
    merge_allow,
    merge_watch,
    save_site_rules,
)


def _patch_policy_paths(tmp_path, monkeypatch):
    monkeypatch.setattr("backend.behavior.softland_policy._PATH", tmp_path / "softland_policy.json")
    monkeypatch.setattr("backend.behavior.softland_policy._LEGACY_SITE", tmp_path / "site.json")
    monkeypatch.setattr("backend.behavior.softland_policy._LEGACY_SCHEDULES", tmp_path / "sched.json")


def test_save_load_and_merge(tmp_path, monkeypatch):
    _patch_policy_paths(tmp_path, monkeypatch)

    saved = save_site_rules({
        "allow_extra": ["Example.COM", "https://foo.org/path", "bad"],
        "watch_extra": ["reddit.com"],
        "block_extra": ["tiktok.com"],
    })
    assert saved["allow_extra"] == ["example.com", "foo.org"]
    assert saved["watch_extra"] == ["reddit.com"]
    assert saved["block_extra"] == ["tiktok.com"]

    loaded = load_site_rules()
    assert loaded == saved

    assert merge_allow(["github.com"]) == ["github.com", "example.com", "foo.org"]
    assert merge_watch(["youtube.com"]) == ["youtube.com", "reddit.com", "tiktok.com"]


def test_allow_domains_for_mode_merges_extras(tmp_path, monkeypatch):
    _patch_policy_paths(tmp_path, monkeypatch)
    save_site_rules({"allow_extra": ["custom-allow.test"], "watch_extra": [], "block_extra": []})

    from backend.behavior.browser_gate_policy import allow_domains_for_mode

    allow = allow_domains_for_mode("study")
    assert "custom-allow.test" in allow


def test_force_watch_hosts_merges_user_extras(tmp_path, monkeypatch):
    _patch_policy_paths(tmp_path, monkeypatch)
    save_site_rules({
        "allow_extra": [],
        "watch_extra": ["reddit.com"],
        "block_extra": ["tiktok.com"],
    })

    from backend.behavior.browser_gate_policy import (
        _host_matches_force_watch,
        build_browser_gate_section,
    )

    section = build_browser_gate_section(
        enabled=True,
        locked=True,
        morning_next="open",
        mode="study",
    )
    assert "reddit.com" in section["force_watch_hosts"]
    assert "tiktok.com" in section["force_watch_hosts"]
    assert section["force_watch_hosts"] == section["watch_domains"]
    assert _host_matches_force_watch("www.reddit.com") is True
    assert _host_matches_force_watch("tiktok.com") is True
