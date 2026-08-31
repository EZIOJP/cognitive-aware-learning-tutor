"""Tests for device-wide hosts block (no system hosts writes)."""

from __future__ import annotations

from backend.behavior.device_block import (
    MARK_BEGIN,
    MARK_END,
    collect_block_domains,
    merge_hosts_content,
    strip_managed_section,
)


def test_collect_block_domains_porn_only():
    domains = collect_block_domains(
        {"enabled": True, "block_porn": True, "block_watch": False, "block_social": False, "extra_domains": []},
    )
    assert "pornhub.com" in domains
    assert "www.pornhub.com" in domains
    assert "youtube.com" not in domains


def test_collect_block_domains_porn_only_no_youtube():
    domains = collect_block_domains(
        {"enabled": True, "block_porn": True, "block_watch": False, "block_social": False, "extra_domains": []},
    )
    assert "pornhub.com" in domains
    assert "youtube.com" not in domains


def test_collect_block_domains_watch_only_when_enabled():
    domains = collect_block_domains(
        {"enabled": True, "block_porn": False, "block_watch": True, "block_social": False, "extra_domains": []},
    )
    assert "youtube.com" in domains


def test_merge_and_strip_hosts_section():
    existing = "127.0.0.1 localhost\n"
    merged = merge_hosts_content(existing, ["evil.com", "www.evil.com"])
    assert MARK_BEGIN in merged
    assert MARK_END in merged
    assert "0.0.0.0 evil.com" in merged
    assert "::1 evil.com" in merged
    stripped = strip_managed_section(merged)
    assert MARK_BEGIN not in stripped
    assert "127.0.0.1 localhost" in stripped


def test_strip_leaves_unmanaged_hosts():
    text = "127.0.0.1 localhost\n# other block\n0.0.0.0 manual.test\n"
    out = strip_managed_section(text)
    assert "manual.test" in out
