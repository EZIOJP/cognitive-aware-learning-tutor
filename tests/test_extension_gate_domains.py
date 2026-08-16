"""Domain match rules mirrored from selftracker-extension/gate_policy.js."""

from __future__ import annotations

DISTRACTION_DOMAINS = [
    "netflix.com",
    "youtube.com",
    "youtu.be",
    "twitch.tv",
    "disneyplus.com",
    "primevideo.com",
    "instagram.com",
    "reddit.com",
    "x.com",
    "twitter.com",
    "tiktok.com",
    "facebook.com",
]


def is_distraction_url(url: str) -> bool:
    from urllib.parse import urlparse

    try:
        host = (urlparse(url).hostname or "").lower()
    except Exception:
        return False
    if host.startswith("www."):
        host = host[4:]
    if not host:
        return False
    for d in DISTRACTION_DOMAINS:
        d = d.removeprefix("www.")
        if host == d or host.endswith("." + d):
            return True
    return False


def test_distraction_domains_match_streaming():
    assert is_distraction_url("https://www.netflix.com/browse")
    assert is_distraction_url("https://www.youtube.com/watch?v=1")
    assert is_distraction_url("https://youtu.be/abc")
    assert is_distraction_url("https://m.youtube.com/")


def test_distraction_domains_allow_work():
    assert not is_distraction_url("https://github.com/obra/superpowers")
    assert not is_distraction_url("https://scaler.com/topics")
    assert not is_distraction_url("https://www.scaler.com/academy/mentee-dashboard/todos")
    assert not is_distraction_url("https://app.scaler.com/")
    assert not is_distraction_url("http://localhost:5173/bible")


def test_js_gate_policy_lists_same_cores():
    from pathlib import Path

    text = Path("selftracker-extension/gate_policy.js").read_text(encoding="utf-8")
    for d in ("netflix.com", "youtube.com", "youtu.be"):
        assert d in text
    for d in ("scaler.com", "bing.com", "google.com", "interviewbit.com"):
        assert d in text
    for d in (
        "numpy.org",
        "pandas.pydata.org",
        "kaggle.com",
        "huggingface.co",
        "scikit-learn.org",
        "pytorch.org",
        "datacamp.com",
        "medium.com",
    ):
        assert d in text


def test_extension_manifest_bumped_for_scaler_fix():
    from pathlib import Path
    import json

    man = json.loads(
        Path("selftracker-extension/manifest.json").read_text(encoding="utf-8")
    )
    # 1.5.18+: 60s per-host temp allow on locked.html
    parts = [int(x) for x in str(man["version"]).split(".")]
    assert parts >= [1, 5, 18]


TEMP_ALLOW_MS = 60_000
_FORCE_WATCH = ("youtube.com", "youtu.be", "netflix.com", "primevideo.com")
_SOCIAL = ("instagram.com", "reddit.com", "x.com", "twitter.com", "tiktok.com", "facebook.com")
_PORN = ("pornhub.com", "xvideos.com", "xnxx.com")


def _norm_host(host: str) -> str:
    h = (host or "").lower().removeprefix("www.")
    return h


def _host_match(host: str, domain: str) -> bool:
    h, d = _norm_host(host), _norm_host(domain)
    if not h or not d:
        return False
    return h == d or h.endswith("." + d)


def is_temp_allow_excluded(host: str) -> bool:
    """Mirror gate_policy.js isTempAllowExcludedHost (force watch/porn + social)."""
    h = _norm_host(host)
    if not h:
        return True
    for d in _FORCE_WATCH + _PORN + _SOCIAL:
        if _host_match(h, d):
            return True
    if h.endswith((".xxx", ".adult", ".porn", ".sex")):
        return True
    return False


def is_host_temp_allowed(host: str, allows: list, now_ms: int) -> bool:
    if is_temp_allow_excluded(host):
        return False
    h = _norm_host(host)
    for e in allows or []:
        eh = _norm_host(str(e.get("host") or ""))
        until = int(e.get("until") or 0)
        if not eh or until <= now_ms:
            continue
        if _host_match(h, eh) or _host_match(eh, h):
            return True
    return False


def test_temp_allow_ms_is_60_seconds():
    from pathlib import Path

    text = Path("selftracker-extension/gate_policy.js").read_text(encoding="utf-8")
    assert "TEMP_ALLOW_MS" in text
    assert "60000" in text
    assert "isHostTempAllowed" in text
    assert "isTempAllowExcludedHost" in text
    assert "buildTempAllowGrant" in text
    assert "Watch sites can't be temporarily allowed" in text
    locked = Path("selftracker-extension/locked.js").read_text(encoding="utf-8")
    assert "Allow this site 60 sec" in locked
    assert "TEMP_ALLOW_REQUEST" in locked
    bg = Path("selftracker-extension/background.js").read_text(encoding="utf-8")
    assert "lockedPageUrlForBlocked" in bg
    assert "TEMP_ALLOW_REQUEST" in bg


def test_temp_allow_excludes_watch_porn_social():
    assert is_temp_allow_excluded("youtube.com")
    assert is_temp_allow_excluded("www.youtube.com")
    assert is_temp_allow_excluded("m.youtube.com")
    assert is_temp_allow_excluded("netflix.com")
    assert is_temp_allow_excluded("pornhub.com")
    assert is_temp_allow_excluded("instagram.com")
    assert is_temp_allow_excluded("reddit.com")
    assert not is_temp_allow_excluded("example-docs.io")
    assert not is_temp_allow_excluded("readthedocs.io")


def test_temp_allow_ttl_and_exclusion_in_check():
    now = 1_700_000_000_000
    allows = [{"host": "docs.example.com", "until": now + TEMP_ALLOW_MS}]
    assert is_host_temp_allowed("docs.example.com", allows, now)
    assert is_host_temp_allowed("www.docs.example.com", allows, now)
    assert not is_host_temp_allowed("docs.example.com", allows, now + TEMP_ALLOW_MS + 1)
    # Even if somehow granted, watch stays excluded
    yt = [{"host": "youtube.com", "until": now + TEMP_ALLOW_MS}]
    assert not is_host_temp_allowed("youtube.com", yt, now)
    assert TEMP_ALLOW_MS == 60_000


def test_py_js_allow_domains_include_ds_sites():
    """Python DEFAULT_ALLOW and JS FALLBACK_ALLOW both list key DS hosts."""
    from pathlib import Path
    from backend.behavior.browser_gate_policy import DEFAULT_ALLOW_DOMAINS

    text = Path("selftracker-extension/gate_policy.js").read_text(encoding="utf-8")
    for d in (
        "numpy.org",
        "pandas.pydata.org",
        "scipy.org",
        "scikit-learn.org",
        "kaggle.com",
        "huggingface.co",
        "fast.ai",
        "deeplearning.ai",
        "paperswithcode.com",
        "deepnote.com",
        "stats.stackexchange.com",
    ):
        assert d in DEFAULT_ALLOW_DOMAINS, d
        assert d in text, d
