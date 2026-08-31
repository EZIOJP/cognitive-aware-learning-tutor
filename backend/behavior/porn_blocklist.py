"""Scrape + cache porn-site domains from theporndude.com directory (index pages only).

Used by desktop tracker for device-wide hosts blocking — porn only, not YouTube.
"""

from __future__ import annotations

import json
import logging
import re
import time
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse

log = logging.getLogger("calt.porn_blocklist")

TPD_BASE = "https://theporndude.com"
TPD_SEED_PATHS: tuple[str, ...] = (
    "/",
    "/top-porn-tube-sites",
    "/top-premium-sites",
    "/free-porn-tube-sites",
    "/free-onlyfans-porn-sites",
    "/best-webcam-sites",
    "/best-escort-sites",
    "/best-vr-porn-sites",
    "/best-games-porn-sites",
    "/best-ai-porn-sites",
)

# Never block these even if linked from TPD index.
SKIP_HOSTS: frozenset[str] = frozenset(
    {
        "theporndude.com",
        "google.com",
        "googleapis.com",
        "gstatic.com",
        "youtube.com",
        "youtu.be",
        "facebook.com",
        "twitter.com",
        "x.com",
        "instagram.com",
        "reddit.com",
        "discord.com",
        "cloudflare.com",
        "amazon.com",
        "apple.com",
        "microsoft.com",
        "wikipedia.org",
        "github.com",
        "localhost",
    }
)

SKIP_SUFFIXES: tuple[str, ...] = (
    ".theporndude.com",
    ".google.com",
    ".googleusercontent.com",
    ".facebook.com",
    ".twitter.com",
)

MAX_DOMAINS = 8000
CACHE_TTL_S = 7 * 24 * 3600
USER_AGENT = "CALT-PornBlocklist/1.0 (+local study tracker; index scrape only)"


class _LinkParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.hrefs: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() != "a":
            return
        for k, v in attrs:
            if k.lower() == "href" and v:
                self.hrefs.append(v.strip())


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def cache_path() -> Path:
    p = _repo_root() / "data" / "behavior" / "porn_blocklist.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def normalize_domain(host: str | None) -> str | None:
    if not host:
        return None
    h = host.lower().strip().removeprefix("www.")
    if not h or h in SKIP_HOSTS:
        return None
    if any(h.endswith(s) for s in SKIP_SUFFIXES):
        return None
    if h.endswith(".local") or h.endswith(".lan"):
        return None
    # Basic sanity — must look like a domain.
    if "." not in h or len(h) < 4:
        return None
    if re.search(r"[^\w.\-]", h):
        return None
    return h


def domain_from_url(url: str, *, base: str = TPD_BASE) -> str | None:
    raw = (url or "").strip()
    if not raw or raw.startswith("#") or raw.startswith("javascript:"):
        return None
    if raw.startswith("/"):
        return None
    if not raw.startswith("http"):
        raw = urljoin(base, raw)
    try:
        parsed = urlparse(raw)
    except ValueError:
        return None
    if parsed.scheme not in ("http", "https"):
        return None
    host = parsed.hostname
    if not host:
        return None
    if "theporndude" in host.lower():
        return None
    return normalize_domain(host)


def extract_domains_from_html(html: str, *, base: str = TPD_BASE) -> set[str]:
    parser = _LinkParser()
    try:
        parser.feed(html)
    except Exception:
        pass
    out: set[str] = set()
    for href in parser.hrefs:
        d = domain_from_url(href, base=base)
        if d:
            out.add(d)
    # Fallback: bare domains in review URLs (some pages embed them in JSON).
    for m in re.finditer(r"https?://([a-z0-9][a-z0-9.-]+\.[a-z]{2,})", html, re.I):
        d = normalize_domain(m.group(1))
        if d:
            out.add(d)
    return out


def discover_category_paths(html: str) -> list[str]:
    paths: set[str] = set(TPD_SEED_PATHS)
    for href in re.findall(r'href=["\'](/[a-z0-9-]+)["\']', html, re.I):
        low = href.lower()
        if any(k in low for k in ("porn", "site", "tube", "cam", "escort", "onlyfans", "hentai", "ai-")):
            paths.add(href.split("?", 1)[0])
    return sorted(paths)[:40]


def scrape_theporndude(*, timeout: float = 25.0) -> dict[str, Any]:
    """Fetch TPD index/category pages and collect outbound site domains."""
    import requests

    from backend.behavior.browser_gate_policy import DEFAULT_PORN_DOMAINS

    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT})

    domains: set[str] = set()
    for seed in DEFAULT_PORN_DOMAINS:
        d = normalize_domain(seed)
        if d:
            domains.add(d)

    fetched_pages: list[str] = []
    errors: list[str] = []

    try:
        home = session.get(TPD_BASE + "/", timeout=timeout)
        home.raise_for_status()
        domains.update(extract_domains_from_html(home.text))
        paths = discover_category_paths(home.text)
    except Exception as exc:
        paths = list(TPD_SEED_PATHS)
        errors.append(f"home: {exc}")

    for path in paths:
        url = TPD_BASE + path if path.startswith("/") else path
        if url in fetched_pages:
            continue
        fetched_pages.append(url)
        try:
            r = session.get(url, timeout=timeout)
            if r.status_code >= 400:
                errors.append(f"{path}: HTTP {r.status_code}")
                continue
            domains.update(extract_domains_from_html(r.text, base=url))
        except Exception as exc:
            errors.append(f"{path}: {exc}")
        time.sleep(0.35)

    sorted_domains = sorted(domains)[:MAX_DOMAINS]
    return {
        "source": "theporndude.com",
        "scraped_at": datetime.now(timezone.utc).isoformat(),
        "domains": sorted_domains,
        "count": len(sorted_domains),
        "pages_fetched": len(fetched_pages),
        "errors": errors[:20],
    }


def load_cache() -> dict[str, Any]:
    path = cache_path()
    if not path.is_file():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def save_cache(payload: dict[str, Any]) -> None:
    cache_path().write_text(json.dumps(payload, indent=2), encoding="utf-8")


def cached_domains() -> list[str]:
    data = load_cache()
    raw = data.get("domains")
    if isinstance(raw, list) and raw:
        return [str(x).lower() for x in raw if str(x).strip()]
    from backend.behavior.browser_gate_policy import DEFAULT_PORN_DOMAINS

    return sorted({normalize_domain(d) for d in DEFAULT_PORN_DOMAINS if normalize_domain(d)})


def cache_age_s() -> float | None:
    data = load_cache()
    raw = data.get("scraped_at")
    if not raw:
        return None
    try:
        ts = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
        return max(0.0, (datetime.now(timezone.utc) - ts).total_seconds())
    except ValueError:
        return None


def refresh_if_stale(*, force: bool = False, max_age_s: float = CACHE_TTL_S) -> dict[str, Any]:
    age = cache_age_s()
    if not force and age is not None and age < max_age_s:
        return {"ok": True, "refreshed": False, "count": len(cached_domains()), "age_s": age}
    try:
        payload = scrape_theporndude()
        save_cache(payload)
        log.info("TPD blocklist refreshed: %s domains", payload.get("count"))
        return {"ok": True, "refreshed": True, **payload}
    except Exception as exc:
        log.warning("TPD scrape failed: %s", exc)
        return {"ok": False, "refreshed": False, "error": str(exc), "count": len(cached_domains())}
