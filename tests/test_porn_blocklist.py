"""Tests for theporndude index parsing (offline fixtures — no network)."""

from __future__ import annotations

from backend.behavior.porn_blocklist import (
    discover_category_paths,
    domain_from_url,
    extract_domains_from_html,
    normalize_domain,
)

SAMPLE_HTML = """
<html><body>
  <a href="https://pornhub.com/">PH</a>
  <a href="https://www.xvideos.com/video">XV</a>
  <a href="https://theporndude.com/pornhub-review">review</a>
  <a href="https://youtube.com/watch?v=1">yt</a>
  <a href="/top-porn-tube-sites">cats</a>
  <a href="/free-onlyfans-porn-sites">of</a>
</body></html>
"""


def test_normalize_skips_youtube_and_tpd():
    assert normalize_domain("youtube.com") is None
    assert normalize_domain("www.theporndude.com") is None
    assert normalize_domain("pornhub.com") == "pornhub.com"


def test_extract_domains_from_fixture():
    found = extract_domains_from_html(SAMPLE_HTML)
    assert "pornhub.com" in found
    assert "xvideos.com" in found
    assert "youtube.com" not in found
    assert "theporndude.com" not in found


def test_discover_category_paths():
    paths = discover_category_paths(SAMPLE_HTML)
    assert "/top-porn-tube-sites" in paths
    assert "/free-onlyfans-porn-sites" in paths


def test_domain_from_url_relative_ignored():
    assert domain_from_url("/local") is None
    assert domain_from_url("https://spankbang.com/x") == "spankbang.com"
