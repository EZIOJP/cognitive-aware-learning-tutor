"""Day-mode → allow/block matrix for SelfTracker browser policy."""

from datetime import datetime, timedelta, timezone

from backend.behavior.browser_gate_policy import (
    build_browser_gate_section,
    classify_browser_url,
    clear_free_override,
    is_evening_free_window,
    is_errands_block,
    is_free_block,
    is_planning_block,
    is_study_block,
    mode_policy_flags,
    resolve_day_mode,
    set_free_override,
    FREE_LIFE_ALLOW_DOMAINS,
)


def _day(h: int, m: int = 0) -> datetime:
    return datetime(2026, 8, 5, h, m, tzinfo=timezone.utc)


def test_resolve_day_mode_morning_first():
    assert resolve_day_mode(morning_next="bible", now=_day(10)) == "bible"
    assert resolve_day_mode(morning_next="plan", now=_day(10)) == "planning"
    assert (
        resolve_day_mode(morning_next="plan", planner_category="study", now=_day(10))
        == "planning"
    )


def test_resolve_day_mode_daytime_defaults_to_study():
    """After plan confirm, gaps are study — not casual free YouTube."""
    assert resolve_day_mode(morning_next="open", now=_day(14), free_override_active=False) == "study"
    assert (
        resolve_day_mode(
            morning_next="open",
            planner_category="study",
            planner_title="LeetCode",
            now=_day(14),
            free_override_active=False,
        )
        == "study"
    )
    assert (
        resolve_day_mode(
            morning_next="open",
            planner_category="focus",
            planner_title="Deep work",
            now=_day(11),
            free_override_active=False,
        )
        == "study"
    )


def test_resolve_day_mode_day_unlimited_unlocks_youtube():
    """Daily focus goal met → free even during a study calendar block."""
    assert (
        resolve_day_mode(
            morning_next="open",
            planner_category="Study / Reading",
            planner_title="Deep work",
            now=_day(14),
            free_override_active=False,
            day_unlimited=True,
        )
        == "free"
    )
    # Morning bible/plan still win over day_unlimited
    assert (
        resolve_day_mode(
            morning_next="bible",
            now=_day(8),
            free_override_active=False,
            day_unlimited=True,
        )
        == "bible"
    )
    section = build_browser_gate_section(
        enabled=True,
        locked=False,
        morning_next="open",
        planner_category="study",
        planner_title="Deep work",
        now=_day(14),
        free_override_active=False,
        day_unlimited=True,
    )
    assert section["mode"] == "free"
    assert section["block_watch_sites"] is False
    assert section["day_unlimited"] is True
    from backend.behavior.browser_gate_policy import classify_browser_url

    hit = classify_browser_url(
        "https://www.youtube.com/watch?v=1",
        enforce=True,
        block_watch_sites=section["block_watch_sites"],
        mode=section["mode"],
    )
    assert hit["action"] != "block"


def test_resolve_day_mode_free_only_in_window_or_block():
    assert (
        resolve_day_mode(
            morning_next="open",
            planner_category="planning",
            planner_title="Week plan",
            now=_day(10),
            free_override_active=False,
        )
        == "planning"
    )
    assert (
        resolve_day_mode(
            morning_next="open",
            planner_category="break",
            now=_day(14),
            free_override_active=False,
        )
        == "free"
    )
    assert (
        resolve_day_mode(
            morning_next="open",
            planner_category="leisure",
            planner_title="Downtime",
            now=_day(15),
            free_override_active=False,
        )
        == "free"
    )
    # Evening window
    assert (
        resolve_day_mode(
            morning_next="open",
            now=_day(21, 30),
            free_override_active=False,
            free_after_hm="21:00",
        )
        == "free"
    )
    # Study block still wins over evening
    assert (
        resolve_day_mode(
            morning_next="open",
            planner_category="study",
            planner_title="Scaler",
            now=_day(21, 30),
            free_override_active=False,
            free_after_hm="21:00",
        )
        == "study"
    )
    # Tray override
    assert (
        resolve_day_mode(morning_next="open", now=_day(10), free_override_active=True) == "free"
    )


def test_is_evening_free_window():
    assert is_evening_free_window(_day(20, 59), free_after_hm="21:00") is False
    assert is_evening_free_window(_day(21, 0), free_after_hm="21:00") is True


def test_free_override_roundtrip(tmp_path):
    path = tmp_path / "browser_free_override.json"
    clear_free_override(path=path)
    now = _day(12)
    until = set_free_override(minutes=30, path=path, now=now)
    assert until == now + timedelta(minutes=30)
    # Active while "now" is before until — free_override_until uses wall clock;
    # write a far-future stamp for the helper check.
    far = datetime.now().astimezone() + timedelta(hours=2)
    path.write_text(
        '{"until": "%s", "minutes": 30}' % far.isoformat(),
        encoding="utf-8",
    )
    from backend.behavior.browser_gate_policy import free_override_until

    assert free_override_until(path=path) is not None
    clear_free_override(path=path)
    assert free_override_until(path=path) is None


def test_is_study_and_planning_helpers():
    assert is_planning_block("plan", "Morning plan")
    assert is_study_block("study", "Scaler lecture")
    assert is_free_block("break", "Coffee break")
    assert is_free_block("leisure", "Downtime")
    assert not is_free_block("personal", "Bath / self-care")
    assert not is_free_block("food", "Lunch")
    assert not is_free_block("meal", "Dinner")
    assert not is_study_block("break", "Coffee break")
    # Short token "plan" must not false-hit inside explanation / plant
    assert not is_planning_block(None, "Explanation of gradients")
    assert not is_planning_block(None, "Plant biology")
    assert not is_planning_block(None, "Food Delivery Data Exploration and analysis 4")
    assert (
        resolve_day_mode(
            morning_next="open",
            planner_title="Explanation of gradients",
            free_override_active=False,
            now=_day(10),
        )
        == "study"
    )
    assert not is_study_block("planning", "Day plan")


def test_personal_and_meal_blocks_resolve_study_not_free():
    """Bath/personal/lunch must NOT unlock YouTube in daytime."""
    now = _day(8, 15)
    assert (
        resolve_day_mode(
            morning_next="open",
            planner_category="personal",
            planner_title="Bath / self-care",
            now=now,
            free_override_active=False,
        )
        == "study"
    )
    assert (
        resolve_day_mode(
            morning_next="open",
            planner_category="food",
            planner_title="Lunch",
            now=now,
            free_override_active=False,
        )
        == "study"
    )
    s = build_browser_gate_section(
        enabled=True,
        locked=True,
        morning_next="open",
        planner_category="personal",
        planner_title="Bath / self-care",
        now=now,
        free_override_active=False,
    )
    assert s["mode"] == "study"
    assert s["block_watch_sites"] is True
    assert (
        classify_browser_url(
            "https://www.youtube.com/watch?v=1",
            mode=s["mode"],
            enforce=s["enforce"],
            block_watch_sites=s["block_watch_sites"],
            block_porn=s["block_porn"],
            block_social=s["block_social"],
            block_keywords=s["block_keywords"],
            block_other=s["block_other"],
            allow_domains=s["allow_domains"],
            watch_domains=s["watch_domains"],
        )["action"]
        == "block"
    )


def _act(url: str, mode: str, title: str = "") -> str:
    flags = mode_policy_flags(mode)
    section = build_browser_gate_section(
        enabled=True,
        locked=False,
        morning_next="open" if mode in ("study", "free") else ("bible" if mode == "bible" else "plan"),
        mode=mode,
    )
    out = classify_browser_url(
        url,
        title=title,
        mode=mode,
        enforce=section["enforce"],
        block_watch_sites=section["block_watch_sites"],
        block_porn=section["block_porn"],
        block_social=section["block_social"],
        block_keywords=section["block_keywords"],
        block_other=section["block_other"],
        strict_allowlist=section["strict_allowlist"],
        allow_domains=section["allow_domains"],
        localhost_path_prefixes=section.get("localhost_path_prefixes") or None,
    )
    return out["action"]


def test_hard_force_youtube_even_if_watch_flag_off():
    """Defense-in-depth: mode=study blocks YT even when block_watch_sites=False."""
    out = classify_browser_url(
        "https://www.youtube.com/",
        mode="study",
        enforce=True,
        block_watch_sites=False,
        block_other=False,
    )
    assert out["action"] == "block"
    assert out["category"] == "watch"


def test_matrix_planning_blocks_all_except_calt():
    assert _act("http://localhost:5173/bible", "planning") == "allow"
    assert _act("http://localhost:5173/productivity", "planning") == "allow"
    assert _act("http://localhost:5173/lecture-notes", "planning") == "allow"
    assert _act("https://www.scaler.com/", "planning") == "allow"
    assert _act("http://localhost:5173/vocab", "planning") == "block"
    assert _act("https://github.com/", "planning") == "block"
    assert _act("https://www.youtube.com/", "planning") == "block"
    assert _act("https://pornhub.com/", "planning") == "block"


def test_matrix_bible_same_as_strict():
    assert _act("http://localhost:5173/bible", "bible") == "allow"
    assert _act("https://colab.research.google.com/", "bible") == "block"
    assert _act("https://www.netflix.com/", "bible") == "block"


def test_matrix_study_allows_goal_blocks_entertainment():
    assert _act("https://colab.research.google.com/drive/1", "study") == "allow"
    assert _act("https://www.scaler.com/", "study") == "allow"
    assert _act("https://app.scaler.com/academy/", "study") == "allow"
    assert _act("https://www.scaler.com/academy/mentee-dashboard/todos", "study") == "allow"
    assert _act("https://github.com/obra/superpowers", "study") == "allow"
    assert _act("https://leetcode.com/problemset", "study") == "allow"
    assert _act("http://localhost:5173/productivity", "study") == "allow"
    assert _act("https://www.youtube.com/watch?v=1", "study") == "block"
    assert _act("https://www.instagram.com/", "study") == "block"
    assert _act("https://pornhub.com/", "study") == "block"
    assert _act("https://example.com/random", "study") == "block"


def test_study_allows_omnibox_search_hops_to_scaler():
    """Edge/Chrome omnibox often commits Bing/Google before scaler.com loads."""
    for url in (
        "https://www.bing.com/search?q=scaler.com",
        "https://www.google.com/search?q=www.scaler.com",
        "https://ntp.msn.com/",
        "https://duckduckgo.com/?q=scaler",
    ):
        assert _act(url, "study") == "allow", url
    # Destination itself
    assert _act("https://www.scaler.com/academy/mentee-dashboard/todos", "study") == "allow"
    # Watch hosts still blocked
    assert _act("https://www.youtube.com/results?search_query=scaler", "study") == "block"


def test_study_allows_scaler_legacy_hosts():
    assert _act("https://www.interviewbit.com/", "study") == "allow"
    assert _act("https://www.scaleracademy.com/", "study") == "allow"


def test_study_mode_blocks_youtube_host():
    """Integration-style: study mode must block youtube.com / youtu.be hosts."""
    for url in (
        "https://www.youtube.com/",
        "https://youtube.com/watch?v=dQw4w9WgXcQ",
        "https://m.youtube.com/watch?v=1",
        "https://youtu.be/dQw4w9WgXcQ",
        "https://music.youtube.com/",
    ):
        assert _act(url, "study") == "block", url
    assert _act("https://www.youtube.com/", "bible") == "block"
    assert _act("https://www.youtube.com/", "planning") == "block"
    # Free still allows YouTube (adult filter only)
    assert _act("https://www.youtube.com/", "free") == "none"


def test_build_section_study_exposes_watch_block():
    s = build_browser_gate_section(
        enabled=True, locked=True, morning_next="open", mode="study"
    )
    assert s["mode"] == "study"
    assert s["block_watch_sites"] is True
    assert "youtube.com" in s["watch_domains"]
    assert "youtu.be" in s["watch_domains"]
    decision = classify_browser_url(
        "https://www.youtube.com/watch?v=1",
        enforce=True,
        block_watch_sites=s["block_watch_sites"],
        block_porn=s["block_porn"],
        block_social=s["block_social"],
        block_keywords=s["block_keywords"],
        block_other=s["block_other"],
        allow_domains=s["allow_domains"],
        watch_domains=s["watch_domains"],
    )
    assert decision["action"] == "block"
    assert decision["category"] == "watch"


def test_matrix_free_porn_only():
    assert _act("https://www.youtube.com/watch?v=1", "free") == "none"
    assert _act("https://www.netflix.com/", "free") == "none"
    assert _act("https://www.instagram.com/", "free") == "none"
    assert _act("https://example.com/", "free") == "none"
    assert _act("https://github.com/", "free") == "allow"
    assert _act("https://pornhub.com/", "free") == "block"
    assert _act("https://example.com/path?q=porn+video", "free") == "block"
    assert _act("https://news.example.com/article", "free", title="Hardcore porn review") == "block"


def test_build_section_exposes_mode():
    s = build_browser_gate_section(
        enabled=True, locked=False, morning_next="open", mode="study"
    )
    assert s["mode"] == "study"
    assert s["mode_label"] == "STUDY"
    assert s["block_other"] is True
    assert s["block_watch_sites"] is True
    assert s["enforce"] is True
    assert s["daytime_default"] == "study"
    assert s["free_after"]

    f = build_browser_gate_section(
        enabled=False, locked=False, morning_next="open", mode="free"
    )
    assert f["mode"] == "free"
    assert f["block_porn"] is True
    assert f["block_watch_sites"] is False
    assert f["block_other"] is False
    assert f["enforce"] is True


def test_build_section_open_daytime_resolves_study():
    s = build_browser_gate_section(
        enabled=True,
        locked=False,
        morning_next="open",
        now=_day(14),
        free_override_active=False,
        free_after_hm="21:00",
    )
    assert s["mode"] == "study"
    assert s["block_watch_sites"] is True


def test_free_allows_amazon_study_blocks_amazon():
    """Shopping OK in free; blocked as other in study unless errands-lite."""
    free = build_browser_gate_section(
        enabled=False, locked=False, morning_next="open", mode="free"
    )
    assert free["allow_free_life"] is True
    assert "amazon.com" in free["allow_domains"]
    assert "amazon.com" in free["free_life_allow_domains"]
    assert (
        classify_browser_url(
            "https://www.amazon.in/dp/B0",
            mode="free",
            enforce=True,
            block_watch_sites=False,
            block_other=False,
            allow_domains=free["allow_domains"],
        )["action"]
        == "allow"
    )

    study = build_browser_gate_section(
        enabled=True, locked=False, morning_next="open", mode="study"
    )
    assert study["allow_free_life"] is False
    assert "amazon.com" not in study["allow_domains"]
    assert (
        classify_browser_url(
            "https://www.amazon.com/",
            mode="study",
            enforce=True,
            block_watch_sites=True,
            block_other=True,
            allow_domains=study["allow_domains"],
        )["action"]
        == "block"
    )


def test_errands_block_free_lite_shopping_not_youtube():
    assert is_errands_block("shopping", "Groceries")
    assert "amazon.com" in FREE_LIFE_ALLOW_DOMAINS
    now = _day(11)
    s = build_browser_gate_section(
        enabled=True,
        locked=False,
        morning_next="open",
        planner_category="shopping",
        planner_title="Amazon errands",
        now=now,
        free_override_active=False,
        free_after_hm="21:00",
    )
    assert s["mode"] == "study"
    assert s["allow_free_life"] is True
    assert s["block_watch_sites"] is True
    assert "amazon.com" in s["allow_domains"]
    assert (
        classify_browser_url(
            "https://www.amazon.com/",
            mode=s["mode"],
            enforce=s["enforce"],
            block_watch_sites=s["block_watch_sites"],
            block_other=s["block_other"],
            allow_domains=s["allow_domains"],
        )["action"]
        == "allow"
    )
    assert (
        classify_browser_url(
            "https://www.youtube.com/watch?v=1",
            mode=s["mode"],
            enforce=s["enforce"],
            block_watch_sites=s["block_watch_sites"],
            block_other=s["block_other"],
            allow_domains=s["allow_domains"],
            watch_domains=s["watch_domains"],
        )["action"]
        == "block"
    )
