"""Keyword filters + canned block dialogues + NSFW scan (mocked)."""

from __future__ import annotations

import random

from backend.behavior.browser_gate_policy import (
    classify_browser_url,
    text_matches_block_keywords,
    url_or_title_hits_keywords,
    build_browser_gate_section,
)
from backend.behavior.distraction_gate import (
    is_allowed_browser,
    is_unauthorized_browser,
)
from backend.behavior.voice_agent.block_dialogues import (
    canonical_kind,
    pick_dialogue,
    lines_for,
    pool_sizes,
    reset_rotate_for_tests,
)
from backend.behavior import gate_alerts
from backend.behavior import nsfw_screen_scan as nsfw


def test_keyword_matches_explicit_terms():
    assert text_matches_block_keywords("Watch BDSM tutorial") == "bdsm"
    assert text_matches_block_keywords("onlyfans.com/user") == "onlyfans"
    assert url_or_title_hits_keywords(
        "https://example.com/search?q=hentai+art", ""
    ) == "hentai"
    assert url_or_title_hits_keywords(
        "https://google.com/search?q=foo", "Free porn videos"
    ) == "porn"


def test_keyword_avoids_short_noise_tokens():
    # "ass" not in default list; "assessment" must not trip "ass"
    assert text_matches_block_keywords("assessment results") is None
    assert text_matches_block_keywords("classic literature") is None
    # allowlist host still wins even with keyword in path
    out = classify_browser_url(
        "https://colab.research.google.com/drive/bdsm-notebook",
        title="bdsm",
        enforce=True,
        block_keywords=True,
    )
    assert out["action"] == "allow"


def test_keyword_blocks_non_allow_url():
    out = classify_browser_url(
        "https://example.com/watch?v=xxx-clip",
        enforce=True,
        block_keywords=True,
    )
    assert out["action"] == "block"
    assert out["category"] == "keyword"
    assert out.get("matched") == "xxx"


def test_browser_gate_section_includes_keywords():
    section = build_browser_gate_section(
        enabled=True, locked=True, morning_next="open"
    )
    assert section["block_keywords"] is True
    assert "bdsm" in section["block_keywords_list"]
    assert "porn" in section["block_keywords_list"]
    assert section["intervals"]["extension_gate_poll_s"] == 4
    assert "msedge.exe" in section["allowed_browsers"]


def test_allowed_browsers_edge_only():
    assert is_allowed_browser("msedge.exe")
    assert not is_allowed_browser("zen.exe")
    assert is_unauthorized_browser("chrome.exe")
    assert is_unauthorized_browser("brave.exe")
    assert is_unauthorized_browser("firefox.exe")
    assert is_unauthorized_browser("zen.exe")
    assert is_unauthorized_browser("ChromeSetup.exe")
    assert not is_unauthorized_browser("msedge.exe")
    assert not is_unauthorized_browser("cursor.exe")


def test_dialogue_picker_canned_no_llm():
    reset_rotate_for_tests()
    sizes = pool_sizes()
    assert sizes["watch_site_block"] >= 8
    assert sizes["porn_or_keyword_block"] >= 8
    assert sizes["unauthorized_browser"] >= 8
    assert sizes["nsfw_screen"] >= 8
    assert sizes["morning_bible_required"] >= 8

    assert canonical_kind("porn") == "porn_or_keyword_block"
    assert canonical_kind("watch") == "watch_site_block"
    assert canonical_kind("morning_bible") == "morning_bible_required"

    rng = random.Random(42)
    a = pick_dialogue("watch_site_block", mode="random", rng=rng)
    b = pick_dialogue("watch", mode="random", rng=rng)
    assert a in lines_for("watch_site_block")
    assert b in lines_for("watch_site_block")
    assert len(a) > 10

    reset_rotate_for_tests()
    r1 = pick_dialogue("nsfw_screen", mode="rotate")
    r2 = pick_dialogue("nsfw_screen", mode="rotate")
    # rotate advances; may wrap but consecutive usually differ when pool > 1
    assert r1 in lines_for("nsfw_screen")
    assert r2 in lines_for("nsfw_screen")


def test_gate_alerts_uses_canned_line(monkeypatch, tmp_path):
    gate_alerts.reset_speak_state_for_tests()
    monkeypatch.setattr(gate_alerts, "_QUEUE_PATH", tmp_path / "pending.json")

    item = gate_alerts.notify_block("watch_site_block")
    assert item["canned"] is True
    assert item["message"] in lines_for("watch_site_block")
    # API only enqueues — tracker drain speaks (avoids double TTS).
    pending = gate_alerts.drain_alerts()
    assert any(p.get("kind") == "watch_site_block" for p in pending)


def test_porn_host_blocked_in_study_and_free():
    """Adult hosts stay blocked in study + free (not only free-mode porn-only)."""
    for mode, enabled in (("study", True), ("free", False), ("bible", False), ("planning", False)):
        section = build_browser_gate_section(
            enabled=enabled,
            locked=False,
            morning_next="open" if mode in ("study", "free") else ("bible" if mode == "bible" else "plan"),
            mode=mode,
        )
        assert section["block_porn"] is True, mode
        assert section["enforce"] is True, mode
        for url in (
            "https://www.pornhub.com/",
            "https://xvideos.com/",
            "https://nhentai.net/g/1",
            "https://www.erome.com/",
            "https://v3.erome.com/",
            "https://video-pool-g.eromecdn.com/",
            "https://eporner.com/",
            "https://foo.xxx/",
        ):
            out = classify_browser_url(
                url,
                enforce=section["enforce"],
                block_porn=section["block_porn"],
                block_watch_sites=section["block_watch_sites"],
                block_keywords=section["block_keywords"],
                block_other=section["block_other"],
                allow_domains=section["allow_domains"],
                porn_domains=section["porn_domains"],
                porn_suffixes=section["porn_suffixes"],
            )
            assert out["action"] == "block", (mode, url, out)
            assert out["category"] == "porn", (mode, url, out)


def test_porn_and_keywords_block_even_when_enforce_false():
    """Adult filter is fail-closed — not gated on Armed/enforce alone."""
    out = classify_browser_url(
        "https://pornhub.com/",
        enforce=False,
        block_porn=True,
    )
    assert out["action"] == "block"
    assert out["category"] == "porn"

    out2 = classify_browser_url(
        "https://example.com/search?q=hentai",
        enforce=False,
        block_porn=True,
        block_keywords=True,
    )
    assert out2["action"] == "block"
    assert out2["category"] == "keyword"


def test_extension_force_porn_hosts_present():
    from pathlib import Path

    text = Path("selftracker-extension/gate_policy.js").read_text(encoding="utf-8")
    assert "FORCE_PORN_HOSTS" in text
    assert "isForcePornHost" in text
    assert "pornhub.com" in text
    # Force-porn must run before the enforce early-return (fail-closed).
    force_idx = text.index("isForcePornHost")
    enforce_early = text.index("if (!enforce) return false;")
    assert force_idx < enforce_early


def test_nsfw_scan_status_inactive_without_model(monkeypatch):
    nsfw.reset_scan_state_for_tests()
    monkeypatch.delenv("NSFW_SCREEN_HEURISTIC", raising=False)
    # Force no real backends
    monkeypatch.setattr(nsfw, "_try_init_classifier", lambda: None)
    monkeypatch.setattr(nsfw, "_classifier", None)
    monkeypatch.setattr(nsfw, "_classifier_name", "none")
    monkeypatch.setattr(nsfw, "_init_attempted", True)
    st = nsfw.scan_status()
    assert st["active"] is False
    assert st["backend"] == "none"
    assert "nudenet" in st["message"].lower() or "onnx" in st["message"].lower()


def test_nsfw_scan_respects_disable_and_interval(monkeypatch):
    nsfw.reset_scan_state_for_tests()
    monkeypatch.setenv("NSFW_SCREEN_SCAN", "0")
    monkeypatch.delenv("VOICE_AGENT_ENABLED", raising=False)
    r = nsfw.maybe_scan_screen(hard_block_armed=True, force=True)
    assert r.ran is False
    assert r.reason == "disabled"

    monkeypatch.setenv("NSFW_SCREEN_SCAN", "")
    monkeypatch.setenv("VOICE_AGENT_ENABLED", "0")
    assert nsfw.should_run_scan(hard_block_armed=True) is False

    monkeypatch.setenv("VOICE_AGENT_ENABLED", "1")
    monkeypatch.delenv("NSFW_SCREEN_SCAN", raising=False)
    assert nsfw.should_run_scan(hard_block_armed=True) is True
    assert nsfw.should_run_scan(hard_block_armed=False) is False
    # Day-mode enforce (study/free) must scan even when hard-block Disarmed
    assert nsfw.should_run_scan(hard_block_armed=False, day_enforce=True) is True

    # Mock capture + classify
    nsfw.reset_scan_state_for_tests()
    monkeypatch.setattr(nsfw, "capture_downscaled_screenshot", lambda: object())
    monkeypatch.setattr(nsfw, "classify_image", lambda img: (0.9, "mock"))
    monkeypatch.setenv("NSFW_SCREEN_THRESHOLD", "0.5")
    out = nsfw.maybe_scan_screen(hard_block_armed=True, force=True, now=1000.0)
    assert out.ran and out.positive
    assert out.backend == "mock"

    # Interval skip
    out2 = nsfw.maybe_scan_screen(hard_block_armed=True, force=False, now=1010.0)
    assert out2.ran is False
    assert out2.reason == "interval"
