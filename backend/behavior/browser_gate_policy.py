"""Browser allow/block lists for SelfTracker extensions (source of truth).

Desktop tracker still kills games only. Extensions poll distraction-gate and
consume the `browser` section for site redirects.

Day modes (after morning bible → plan confirm):
  - **study** (default daytime): goal allowlist; YouTube/Netflix/social blocked.
    Scaler/Colab/GitHub are *allowed* — nothing auto-opens Scaler.
  - **free**: daily focus goal met (``day_unlimited``), explicit planner
    break/leisure blocks, after ``BROWSER_FREE_AFTER`` (default 21:00), or
    tray “Free time” PIN override.
  - Porn + adult keywords stay blocked in every mode when extensions enforce.

Keywords (URL path/query + page/window title) are cheap text filters — not
keylogging. Optional NSFW screenshot scan lives in ``nsfw_screen_scan``
(occasional CPU; off when disarmed / gaming silence).
"""

from __future__ import annotations

import json
import os
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse

from backend.paths import ROOT

# Soft-landing SPA URLs (overridable via env).
DEFAULT_BIBLE_URL = os.environ.get("CALT_BIBLE_URL", "http://localhost:5173/bible").rstrip("/")
DEFAULT_PLAN_URL = os.environ.get(
    "CALT_PRODUCTIVITY_URL", "http://localhost:5173/productivity?tab=plan"
).rstrip("/")

# Productive study/work — allowlist always wins over block lists.
DEFAULT_ALLOW_DOMAINS: tuple[str, ...] = (
    "localhost",
    "127.0.0.1",
    "colab.research.google.com",
    "scaler.com",
    # Scaler legacy / sister hosts (InterviewBit era + academy branding)
    "interviewbit.com",
    "scaleracademy.com",
    # Scaler lecture PDF / attachment buckets (virtual-hosted S3).
    # Broader scaler-*.s3.*.amazonaws.com matched via is_scaler_attachment_host().
    "scaler-production-new.s3.ap-southeast-1.amazonaws.com",
    "github.com",
    "githubusercontent.com",
    "gitlab.com",
    "stackoverflow.com",
    "stackexchange.com",
    "docs.google.com",
    "drive.google.com",
    "drive.usercontent.google.com",
    "sheets.google.com",
    "slides.google.com",
    "meet.google.com",
    "classroom.google.com",
    # Google account login + Gemini (needed so Drive/Gemini aren't bounced as "other")
    "accounts.google.com",
    "myaccount.google.com",
    "gemini.google.com",
    "aistudio.google.com",
    "bard.google.com",
    "googleusercontent.com",
    # Omnibox / new-tab search hops (Edge→Bing, Chrome→Google). Without these,
    # typing scaler.com soft-lands the search interstitial as "restricted" even
    # though the destination is allowlisted. YouTube/Netflix hosts stay blocked.
    "google.com",
    "bing.com",
    "duckduckgo.com",
    "search.brave.com",
    "ntp.msn.com",
    "msn.com",
    "notion.so",
    "notion.site",
    "leetcode.com",
    "codeforces.com",
    "atcoder.jp",
    "hackerrank.com",
    "coursera.org",
    "udemy.com",
    "edx.org",
    "khanacademy.org",
    "brilliant.org",
    "arxiv.org",
    "wikipedia.org",
    "developer.mozilla.org",
    "mdn.io",
    "python.org",
    "docs.python.org",
    "pypi.org",
    "npmjs.com",
    "vscode.dev",
    "cursor.com",
    "chatgpt.com",
    "claude.ai",
    "openai.com",
    "anthropic.com",
    "figma.com",
    "excalidraw.com",
    "obsidian.md",
    "zoom.us",
    "web.whatsapp.com",  # light allow — messaging for study groups
    # Data science / AI learning (NumPy, Pandas, courses, notebooks)
    "numpy.org",
    "pandas.pydata.org",
    "scipy.org",
    "scikit-learn.org",
    "matplotlib.org",
    "seaborn.pydata.org",
    "plotly.com",
    "pytorch.org",
    "tensorflow.org",
    "keras.io",
    "huggingface.co",
    "jax.dev",
    "readthedocs.io",
    "polars.tech",
    "realpython.com",
    "pydata.org",
    "kaggle.com",
    "datacamp.com",
    "towardsdatascience.com",
    "medium.com",  # TDS / many DS articles redirect here
    "fast.ai",
    "course.fast.ai",
    "deeplearning.ai",
    "paperswithcode.com",
    "distill.pub",
    "ocw.mit.edu",
    "cs231n.stanford.edu",
    "statisticsbyjim.com",
    "paperspace.com",
    "deepnote.com",
    "databricks.com",
    "stats.stackexchange.com",
    "datascience.stackexchange.com",
)

# Streaming / watch — blocked when Armed or morning locked (block_watch_sites).
DEFAULT_WATCH_DOMAINS: tuple[str, ...] = (
    "youtube.com",
    "youtu.be",
    "netflix.com",
    "primevideo.com",
    "hotstar.com",
    "disneyplus.com",
    "hulu.com",
    "twitch.tv",
    "crunchyroll.com",
    "sonyliv.com",
    "zee5.com",
)

# Distraction / NSFW domain seed (always blocked — free mode too).
DEFAULT_PORN_DOMAINS: tuple[str, ...] = (
    "pornhub.com",
    "xvideos.com",
    "xnxx.com",
    "xhamster.com",
    "redtube.com",
    "youporn.com",
    "tube8.com",
    "spankbang.com",
    "chaturbate.com",
    "onlyfans.com",
    "porn.com",
    "sex.com",
    "hentaihaven.xxx",
    "nhentai.net",
    "rule34.xxx",
    # Common hosts that used to slip through (not on mega-lists)
    "erome.com",
    "eporner.com",
    "hqporner.com",
    "porntrex.com",
    "beeg.com",
    "txxx.com",
    "redgifs.com",
    "imagefap.com",
    "motherless.com",
    "fapello.com",
    "missav.com",
    "jable.tv",
    "thisvid.com",
    "xhamster2.com",
    "xhamster3.com",
    "xvideos2.com",
    "xnxx.tv",
    "pornhub.org",
    "pornhub.net",
)

DEFAULT_PORN_SUFFIXES: tuple[str, ...] = (
    ".xxx",
    ".adult",
    ".porn",
    ".sex",
)

# Soft social distractions (optional block alongside watch while enforcing).
DEFAULT_SOCIAL_DOMAINS: tuple[str, ...] = (
    "instagram.com",
    "reddit.com",
    "x.com",
    "twitter.com",
    "tiktok.com",
    "facebook.com",
    "www.facebook.com",
)

# Adult / NSFW keyword seed — expandable. Prefer multi-char / explicit terms.
# Avoid bare short tokens like "ass" / "sex" (too noisy on normal pages).
DEFAULT_BLOCK_KEYWORDS: tuple[str, ...] = (
    "bdsm",
    "porn",
    "porno",
    "pornography",
    "xxx",
    "onlyfans",
    "fansly",
    "manyvids",
    "chaturbate",
    "stripchat",
    "hentai",
    "nsfw",
    "nude",
    "nudes",
    "nudity",
    "fetish",
    "bondage",
    "pegging",
    "blowjob",
    "handjob",
    "deepthroat",
    "cumshot",
    "creampie",
    "gangbang",
    "threesome",
    "milf",
    "incest",
    "rule34",
    "rule 34",
    "xhamster",
    "xvideos",
    "pornhub",
    "redtube",
    "youporn",
    "spankbang",
    "erome",
    "eporner",
    "hqporner",
    "redgifs",
    "camgirl",
    "cam girl",
    "sex cam",
    "live sex",
    "sex tape",
    "sex video",
    "adult video",
    "erotic",
    "erotica",
    "hardcore porn",
    "naked photo",
    "naked pics",
    "nude photo",
    "nude pics",
    "xxx video",
)


def _keyword_patterns(keywords: tuple[str, ...] | list[str]) -> list[tuple[str, re.Pattern[str]]]:
    out: list[tuple[str, re.Pattern[str]]] = []
    for raw in keywords:
        kw = (raw or "").strip().lower()
        if not kw or len(kw) < 3:
            continue
        # Word-boundary-ish: avoid matching inside longer alphanumerics ("assessment").
        pat = re.compile(
            rf"(?<![a-z0-9]){re.escape(kw)}(?![a-z0-9])",
            re.IGNORECASE,
        )
        out.append((kw, pat))
    return out


_COMPILED_DEFAULT_KEYWORDS = _keyword_patterns(DEFAULT_BLOCK_KEYWORDS)


def normalize_keyword_haystack(*parts: str | None) -> str:
    """Lowercase + URL-decode text for keyword matching."""
    chunks: list[str] = []
    for p in parts:
        if not p:
            continue
        try:
            chunks.append(unquote(str(p)))
        except Exception:  # noqa: BLE001
            chunks.append(str(p))
    return " ".join(chunks).lower()


def text_matches_block_keywords(
    text: str,
    keywords: tuple[str, ...] | list[str] | None = None,
) -> str | None:
    """Return the matched keyword (lowercase) or None.

    Case-insensitive. Uses boundary-aware matching so short seeds do not
    false-trip inside longer words. Empty / very short keyword entries skipped.
    """
    hay = normalize_keyword_haystack(text)
    if not hay:
        return None
    if keywords is None:
        compiled = _COMPILED_DEFAULT_KEYWORDS
    else:
        compiled = _keyword_patterns(keywords)
    for kw, pat in compiled:
        if pat.search(hay):
            return kw
    return None


def url_or_title_hits_keywords(
    url: str = "",
    title: str = "",
    keywords: tuple[str, ...] | list[str] | None = None,
) -> str | None:
    """Check URL (host/path/query) + optional page/window title for block keywords."""
    return text_matches_block_keywords(
        normalize_keyword_haystack(url, title),
        keywords=keywords,
    )


def host_matches_domain(host: str, domain: str) -> bool:
    """True if host equals domain or is a subdomain (not suffix spoof)."""
    h = (host or "").strip().lower().removeprefix("www.")
    d = (domain or "").strip().lower().removeprefix("www.")
    if not h or not d:
        return False
    return h == d or h.endswith("." + d)


def is_scaler_attachment_host(host: str) -> bool:
    """Scaler lecture attachments on S3 (not all of amazonaws.com).

    Example: scaler-production-new.s3.ap-southeast-1.amazonaws.com
    """
    h = (host or "").strip().lower().removeprefix("www.")
    if not h.endswith(".amazonaws.com"):
        return False
    # Virtual-hosted–style: <bucket>.s3.<region>.amazonaws.com
    if ".s3." not in h:
        return False
    bucket = h.split(".", 1)[0]
    return bucket.startswith("scaler")


def hostname_from_url(url: str) -> str:
    try:
        host = urlparse(url).hostname or ""
    except Exception:  # noqa: BLE001
        return ""
    return host.lower().removeprefix("www.")


def _match_any(host: str, domains: tuple[str, ...] | list[str]) -> bool:
    return any(host_matches_domain(host, d) for d in domains)


def classify_browser_host(
    host: str,
    *,
    allow_domains: tuple[str, ...] | list[str] | None = None,
    watch_domains: tuple[str, ...] | list[str] | None = None,
    porn_domains: tuple[str, ...] | list[str] | None = None,
    porn_suffixes: tuple[str, ...] | list[str] | None = None,
    social_domains: tuple[str, ...] | list[str] | None = None,
) -> dict[str, str]:
    """Classify a hostname. Allowlist wins. Returns action allow|block|none + category."""
    h = (host or "").strip().lower().removeprefix("www.")
    if not h:
        return {"action": "none", "category": "other"}

    allow = tuple(allow_domains) if allow_domains is not None else DEFAULT_ALLOW_DOMAINS
    watch = tuple(watch_domains) if watch_domains is not None else DEFAULT_WATCH_DOMAINS
    porn = tuple(porn_domains) if porn_domains is not None else DEFAULT_PORN_DOMAINS
    suffixes = tuple(porn_suffixes) if porn_suffixes is not None else DEFAULT_PORN_SUFFIXES
    social = tuple(social_domains) if social_domains is not None else DEFAULT_SOCIAL_DOMAINS

    if (
        _match_any(h, allow)
        or h in {"localhost", "127.0.0.1"}
        or is_scaler_attachment_host(h)
    ):
        return {"action": "allow", "category": "allow"}

    if _match_any(h, porn) or any(h.endswith(s) for s in suffixes):
        return {"action": "block", "category": "porn"}

    if _match_any(h, watch):
        # amazon.com is broad — only treat as watch if we listed it; keep as watch category
        return {"action": "block", "category": "watch"}

    if _match_any(h, social):
        return {"action": "block", "category": "social"}

    return {"action": "none", "category": "other"}


# Day browser modes (source of truth for SelfTracker + gate UI).
DAY_MODES: tuple[str, ...] = ("bible", "planning", "study", "free")

# Strict morning / planning — localhost SPA paths plus the approved live
# lecture-capture destination. Transcript Studio is a local application and is
# never browser-redirected or process-killed by the tracker.
STRICT_ALLOW_DOMAINS: tuple[str, ...] = ("localhost", "127.0.0.1")
CAPTURE_WORKFLOW_ALLOW_DOMAINS: tuple[str, ...] = (
    "scaler.com",
    "interviewbit.com",
    "scaleracademy.com",
)
STRICT_LOCALHOST_PATH_PREFIXES: tuple[str, ...] = (
    "/bible",
    "/productivity",
    "/login",
    "/lecture-notes",
)

# Planner category / title hints → study or planning blocks.
_STUDY_CATEGORY_TOKENS: frozenset[str] = frozenset(
    {
        "study",
        "focus",
        "deep_work",
        "deepwork",
        "deep work",
        "work",
        "lecture",
        "coding",
        "code",
        "reading",
        "review",
        "math",
        "gre",
        "exam",
        "assignment",
        "project",
        "practice",
        "leetcode",
        "course",
        "homework",
        "research",
    }
)
_PLANNING_CATEGORY_TOKENS: frozenset[str] = frozenset(
    {
        "planning",
        "plan",
        "morning_plan",
        "morning plan",
        "goals",
        "day plan",
    }
)
# Life blocks (bath, meals, gym, commute) are NOT free browsing — daytime stays
# study so YouTube/Netflix stay blocked. Only explicit leisure/break unlocks YT
# before BROWSER_FREE_AFTER (plus tray PIN override).
_LIFE_BLOCK_TOKENS: frozenset[str] = frozenset(
    {
        "meal",
        "lunch",
        "dinner",
        "breakfast",
        "food",
        "sleep",
        "nap",
        "personal",
        "self care",
        "selfcare",
        "gym",
        "exercise",
        "commute",
        "bath",
        "chore",
        "errand",
    }
)
# Shopping / house / errands — allowed in free mode (and errands-lite).
FREE_LIFE_ALLOW_DOMAINS: tuple[str, ...] = (
    "amazon.com",
    "amazon.in",
    "flipkart.com",
    "myntra.com",
    "ajio.com",
    "bigbasket.com",
    "blinkit.com",
    "swiggy.com",
    "zomato.com",
    "ikea.com",
    "housing.com",
    "magicbricks.com",
    "nobroker.in",
    "99acres.com",
    "nykaa.com",
    "meesho.com",
)

_ERRANDS_CATEGORY_TOKENS: frozenset[str] = frozenset(
    {
        "shopping",
        "errands",
        "errand",
        "groceries",
        "household",
        "chores",
        "house",
    }
)
_FREE_BROWSER_TOKENS: frozenset[str] = frozenset(
    {
        "break",
        "rest",
        "free",
        "leisure",
        "downtime",
        "free time",
        "freetime",
    }
)

# Legacy alias — study exclusion still treats life + free as non-study work.
_BREAK_CATEGORY_TOKENS: frozenset[str] = _LIFE_BLOCK_TOKENS | _FREE_BROWSER_TOKENS


def mode_label(mode: str | None) -> str:
    m = (mode or "free").strip().lower()
    return {
        "bible": "BIBLE",
        "planning": "PLANNING",
        "study": "STUDY",
        "free": "FREE",
    }.get(m, "FREE")


def _token_hit(hay: str, tokens: frozenset[str]) -> bool:
    """Match planner category/title tokens without short-substring false hits.

    Short tokens like ``plan`` must not match inside ``explanation`` / ``plant``.
    Multi-word tokens and longer needles still use substring containment.
    """
    h = (hay or "").strip().lower().replace("-", " ").replace("_", " ")
    if not h:
        return False
    if h in tokens:
        return True
    compact = h.replace(" ", "_")
    if compact in {t.replace(" ", "_") for t in tokens}:
        return True
    for t in tokens:
        tl = t.strip().lower()
        if not tl:
            continue
        if " " in tl or "_" in tl or len(tl) >= 6:
            if tl in h or tl.replace(" ", "_") in compact:
                return True
            continue
        if len(tl) >= 4 and re.search(
            rf"(?<![a-z0-9]){re.escape(tl)}(?![a-z0-9])", h
        ):
            return True
    return False


def is_planning_block(category: str | None = None, title: str | None = None) -> bool:
    return _token_hit(category or "", _PLANNING_CATEGORY_TOKENS) or _token_hit(
        title or "", _PLANNING_CATEGORY_TOKENS
    )


def is_study_block(category: str | None = None, title: str | None = None) -> bool:
    if is_planning_block(category, title):
        return False
    if _token_hit(category or "", _BREAK_CATEGORY_TOKENS):
        return False
    if _token_hit(category or "", _STUDY_CATEGORY_TOKENS):
        return True
    # Default planner category is "study"; treat unknown work-ish titles as study
    # when category is empty/study-like.
    cat = (category or "").strip().lower()
    if cat in ("", "study") and (title or "").strip():
        if _token_hit(title or "", _BREAK_CATEGORY_TOKENS):
            return False
        return True
    return False


def is_errands_block(category: str | None = None, title: str | None = None) -> bool:
    """Explicit shopping/errands → free-lite (shopping OK, YouTube still blocked)."""
    if is_planning_block(category, title) or is_free_block(category, title):
        return False
    return _token_hit(category or "", _ERRANDS_CATEGORY_TOKENS) or _token_hit(
        title or "", _ERRANDS_CATEGORY_TOKENS
    )


def is_free_block(category: str | None = None, title: str | None = None) -> bool:
    """Explicit break / leisure / free blocks → browser free mode (YouTube OK).

    Meals, personal/self-care, gym, commute do **not** unlock watch sites —
    daytime default remains study.
    """
    if is_planning_block(category, title):
        return False
    # Prefer category signal; title "Lunch" alone must not unlock YouTube.
    if _token_hit(category or "", _FREE_BROWSER_TOKENS):
        return True
    if _token_hit(title or "", _FREE_BROWSER_TOKENS) and not _token_hit(
        category or "", _LIFE_BLOCK_TOKENS
    ):
        # Title says break/leisure and category is empty or also free-ish.
        cat = (category or "").strip().lower()
        if cat in ("", "break", "rest", "free", "leisure", "downtime"):
            return True
    return False


# Evening free window (local). Daytime default after plan confirm is study.
DEFAULT_BROWSER_FREE_AFTER = "21:00"
_FREE_OVERRIDE_PATH = ROOT / "data" / "browser_free_override.json"
_FREE_OVERRIDE_DEFAULT_MIN = 90


def browser_free_after_hm() -> str:
    raw = (os.environ.get("BROWSER_FREE_AFTER") or DEFAULT_BROWSER_FREE_AFTER).strip()
    return raw or DEFAULT_BROWSER_FREE_AFTER


def parse_hhmm(value: str | None, *, default: str = DEFAULT_BROWSER_FREE_AFTER) -> tuple[int, int]:
    raw = (value or default).strip() or default
    try:
        parts = raw.split(":")
        h = int(parts[0])
        m = int(parts[1]) if len(parts) > 1 else 0
        if 0 <= h <= 23 and 0 <= m <= 59:
            return h, m
    except (TypeError, ValueError):
        pass
    return 21, 0


def is_evening_free_window(
    now: datetime | None = None,
    *,
    free_after_hm: str | None = None,
) -> bool:
    """True when local clock is at/after BROWSER_FREE_AFTER (default 21:00)."""
    dt = now if now is not None else datetime.now().astimezone()
    if dt.tzinfo is None:
        dt = dt.astimezone()
    hh, mm = parse_hhmm(free_after_hm or browser_free_after_hm())
    return (dt.hour, dt.minute) >= (hh, mm)


def free_override_until(*, path: Path | None = None) -> datetime | None:
    """Active tray PIN free-time override end (local tz), or None."""
    store = path if path is not None else _FREE_OVERRIDE_PATH
    try:
        raw = store.read_text(encoding="utf-8")
        data = json.loads(raw) if raw.strip() else {}
    except (OSError, json.JSONDecodeError):
        return None
    until_s = str(data.get("until") or "").strip()
    if not until_s:
        return None
    try:
        until = datetime.fromisoformat(until_s)
    except ValueError:
        return None
    if until.tzinfo is None:
        until = until.astimezone()
    now = datetime.now().astimezone()
    if until <= now:
        return None
    return until


def set_free_override(
    *,
    minutes: int | None = None,
    path: Path | None = None,
    now: datetime | None = None,
) -> datetime:
    """Grant free browsing until now+minutes (default 90). Returns until."""
    store = path if path is not None else _FREE_OVERRIDE_PATH
    mins = minutes if minutes is not None else int(
        os.environ.get("BROWSER_FREE_OVERRIDE_MINUTES") or _FREE_OVERRIDE_DEFAULT_MIN
    )
    mins = max(5, min(mins, 12 * 60))
    dt = now if now is not None else datetime.now().astimezone()
    if dt.tzinfo is None:
        dt = dt.astimezone()
    until = dt + timedelta(minutes=mins)
    store.parent.mkdir(parents=True, exist_ok=True)
    store.write_text(
        json.dumps({"until": until.isoformat(), "minutes": mins}, indent=2),
        encoding="utf-8",
    )
    return until


def clear_free_override(*, path: Path | None = None) -> None:
    store = path if path is not None else _FREE_OVERRIDE_PATH
    try:
        if store.exists():
            store.unlink()
    except OSError:
        pass


def resolve_day_mode(
    *,
    morning_next: str,
    planner_category: str | None = None,
    planner_title: str | None = None,
    now: datetime | None = None,
    free_override_active: bool | None = None,
    free_after_hm: str | None = None,
    day_unlimited: bool = False,
) -> str:
    """Resolve browser day mode from morning gate + planner + evening/override.

    After plan confirm (``morning_next=open``), daytime default is **study**
    (not free) — even with no calendar block, and even during personal/meal/
    gym blocks. Free when: daily focus goal met (``day_unlimited``), explicit
    break/leisure category, evening window (``BROWSER_FREE_AFTER``), or tray
    free-time PIN override.
    """
    next_step = (morning_next or "open").strip().lower()
    if next_step == "bible":
        return "bible"
    if next_step == "plan":
        return "planning"

    dt = now if now is not None else datetime.now().astimezone()
    if free_override_active is None:
        free_override_active = free_override_until() is not None
    if free_override_active:
        return "free"

    # Daily productive goal + Bible chapter → entertainment for the rest of the day
    # (same unlock as desktop games). Morning bible/plan above still win.
    if day_unlimited:
        return "free"

    sched = None
    try:
        from backend.behavior.gate_schedules import scheduled_mode

        sched = scheduled_mode(dt)
    except Exception:
        sched = None
    if sched:
        return sched

    try:
        from backend.behavior.study_mode_nudge import study_nudge_active

        if study_nudge_active():
            return "study"
    except Exception:
        pass

    if is_planning_block(planner_category, planner_title):
        return "planning"
    if is_free_block(planner_category, planner_title):
        return "free"
    if is_study_block(planner_category, planner_title):
        return "study"
    if is_evening_free_window(dt, free_after_hm=free_after_hm):
        return "free"
    # Daytime / gaps between blocks: study allowlist, not casual YouTube.
    return "study"


def mode_policy_flags(mode: str) -> dict[str, bool]:
    """Per-mode block flags (extensions consume these)."""
    m = (mode or "free").strip().lower()
    if m in ("bible", "planning"):
        return {
            "block_other": True,
            "block_watch_sites": True,
            "block_social": True,
            "block_porn": True,
            "block_keywords": True,
            "strict_allowlist": True,
        }
    if m == "study":
        return {
            "block_other": True,
            "block_watch_sites": True,
            "block_social": True,
            "block_porn": True,
            "block_keywords": True,
            "strict_allowlist": False,
        }
    # free — porn + adult keywords only
    return {
        "block_other": False,
        "block_watch_sites": False,
        "block_social": False,
        "block_porn": True,
        "block_keywords": True,
        "strict_allowlist": False,
    }


def allow_domains_for_mode(mode: str) -> list[str]:
    m = (mode or "free").strip().lower()
    if m in ("bible", "planning"):
        return list((*STRICT_ALLOW_DOMAINS, *CAPTURE_WORKFLOW_ALLOW_DOMAINS))
    if m == "free":
        # Free merges shopping/house domains into the effective allow list.
        return list(dict.fromkeys([*DEFAULT_ALLOW_DOMAINS, *FREE_LIFE_ALLOW_DOMAINS]))
    return list(DEFAULT_ALLOW_DOMAINS)


def merge_free_life_domains(allow: list[str] | tuple[str, ...]) -> list[str]:
    """Append FREE_LIFE domains without duplicates (order preserved)."""
    return list(dict.fromkeys([*(allow or []), *FREE_LIFE_ALLOW_DOMAINS]))


def localhost_path_allowed(
    url: str,
    *,
    prefixes: tuple[str, ...] | list[str] | None = None,
) -> bool:
    """True when URL is localhost/127.0.0.1 under an allowed SPA path prefix."""
    try:
        parsed = urlparse(url)
    except Exception:  # noqa: BLE001
        return False
    host = (parsed.hostname or "").lower().removeprefix("www.")
    if host not in {"localhost", "127.0.0.1"}:
        return False
    path = parsed.path or "/"
    allowed = tuple(prefixes) if prefixes is not None else STRICT_LOCALHOST_PATH_PREFIXES
    for p in allowed:
        pref = (p or "/").rstrip("/") or "/"
        if path == pref or path.startswith(pref + "/"):
            return True
    return False


def extension_should_enforce(
    *,
    enabled: bool,
    locked: bool,
    morning_next: str,
    mode: str | None = None,
) -> bool:
    """True when SelfTracker should apply site redirects.

    Day modes always enforce (free = porn/keywords only). Legacy: morning
    bible/plan or Armed still force enforce when mode omitted.
    """
    _ = locked
    if mode:
        return (mode or "").strip().lower() in DAY_MODES
    next_step = (morning_next or "open").strip().lower()
    if next_step in ("bible", "plan"):
        return True
    return bool(enabled)


# Always hard-blocked in bible / planning / study (even if flags glitch).
FORCE_WATCH_HOSTS: tuple[str, ...] = (
    "youtube.com",
    "youtu.be",
    "netflix.com",
    "primevideo.com",
    "hotstar.com",
    "disneyplus.com",
    "hulu.com",
    "twitch.tv",
)


def _host_matches_force_watch(host: str) -> bool:
    h = (host or "").lower().removeprefix("www.")
    if not h:
        return False
    for d in FORCE_WATCH_HOSTS:
        if h == d or h.endswith("." + d):
            return True
    return False


def classify_browser_url(
    url: str,
    *,
    title: str = "",
    enforce: bool = True,
    block_watch_sites: bool = True,
    block_porn: bool = True,
    block_social: bool = True,
    block_keywords: bool = True,
    block_other: bool = False,
    strict_allowlist: bool = False,
    mode: str | None = None,
    allow_domains: tuple[str, ...] | list[str] | None = None,
    watch_domains: tuple[str, ...] | list[str] | None = None,
    porn_domains: tuple[str, ...] | list[str] | None = None,
    porn_suffixes: tuple[str, ...] | list[str] | None = None,
    social_domains: tuple[str, ...] | list[str] | None = None,
    keywords: tuple[str, ...] | list[str] | None = None,
    localhost_path_prefixes: tuple[str, ...] | list[str] | None = None,
) -> dict[str, str]:
    """Decide whether an extension should redirect this URL under current flags.

    Allowlist always wins (with optional localhost path restriction in strict
    modes). Keyword hits on path/query/title count as block category
    ``keyword`` when ``block_keywords`` is on. ``block_other`` blocks any
    non-allowlisted host (study / planning / bible).

    When ``mode`` ∈ {bible, planning, study}, YouTube/Netflix hosts are
    hard-blocked regardless of ``block_watch_sites``.
    """
    host = hostname_from_url(url) if "://" in (url or "") else (url or "").lower()
    allow = tuple(allow_domains) if allow_domains is not None else DEFAULT_ALLOW_DOMAINS
    if strict_allowlist:
        allow = tuple(STRICT_ALLOW_DOMAINS) if allow_domains is None else allow

    base = classify_browser_host(
        host,
        allow_domains=allow,
        watch_domains=watch_domains,
        porn_domains=porn_domains,
        porn_suffixes=porn_suffixes,
        social_domains=social_domains,
    )
    m = (mode or "").strip().lower()
    strict_day = m in ("bible", "planning", "study")
    # Hard-force watch hosts in day-strict modes (before allowlist — YT never allowed).
    if strict_day and (_host_matches_force_watch(host) or base["category"] == "watch"):
        return {"action": "block", "category": "watch"}
    if base["action"] == "allow":
        if strict_allowlist and host in {"localhost", "127.0.0.1"}:
            if not localhost_path_allowed(url, prefixes=localhost_path_prefixes):
                if not enforce:
                    return {"action": "none", "category": "other"}
                return {"action": "block", "category": "other"}
        return base
    # Adult filter is fail-closed: porn hosts + keywords always block when flags
    # are on — even if Armed/enforce is off (matches extension FORCE_PORN).
    if base["category"] == "porn" and block_porn:
        return {"action": "block", "category": "porn"}
    if block_keywords:
        hit = url_or_title_hits_keywords(url, title, keywords=keywords)
        if hit:
            return {"action": "block", "category": "keyword", "matched": hit}
    if not enforce:
        return {"action": "none", "category": base["category"]}
    if base["category"] == "watch" and block_watch_sites:
        return {"action": "block", "category": "watch"}
    if base["category"] == "social" and block_social:
        return {"action": "block", "category": "social"}
    if block_other:
        return {"action": "block", "category": "other"}
    return {"action": "none", "category": base["category"]}


def resolve_browser_redirect(
    *,
    morning_next: str,
    locked: bool,
    enabled: bool,
    mode: str | None = None,
    bible_url: str | None = None,
    plan_url: str | None = None,
) -> dict[str, Any]:
    """Soft-landing URL + reason for locked.html / tab redirects."""
    bible = (bible_url or DEFAULT_BIBLE_URL).rstrip("/")
    plan = (plan_url or DEFAULT_PLAN_URL).rstrip("/")
    next_step = (morning_next or "open").strip().lower()
    m = (mode or "").strip().lower()
    if next_step == "bible" or m == "bible":
        return {
            "redirect_url": bible,
            "redirect_reason": "morning_bible",
            "bible_url": bible,
            "plan_url": plan,
        }
    if next_step == "plan" or m == "planning":
        return {
            "redirect_url": plan,
            "redirect_reason": "morning_plan",
            "bible_url": bible,
            "plan_url": plan,
        }
    if m == "study" or enabled:
        # Soft-landing is extension locked.html; keep bible/plan URLs for links.
        return {
            "redirect_url": None,
            "redirect_reason": "armed_distraction" if enabled else "study_mode",
            "bible_url": bible,
            "plan_url": plan,
        }
    return {
        "redirect_url": None,
        "redirect_reason": None,
        "bible_url": bible,
        "plan_url": plan,
    }


def build_browser_gate_section(
    *,
    enabled: bool,
    locked: bool,
    morning_next: str,
    mode: str | None = None,
    planner_category: str | None = None,
    planner_title: str | None = None,
    bible_url: str | None = None,
    plan_url: str | None = None,
    block_watch_sites: bool | None = None,
    block_porn: bool | None = None,
    block_social: bool | None = None,
    block_keywords: bool | None = None,
    block_other: bool | None = None,
    now: datetime | None = None,
    free_override_active: bool | None = None,
    free_after_hm: str | None = None,
    day_unlimited: bool = False,
) -> dict[str, Any]:
    """Payload nested under distraction-gate as `browser`."""
    free_hm = free_after_hm or browser_free_after_hm()
    override_on = (
        bool(free_override_active)
        if free_override_active is not None
        else free_override_until() is not None
    )
    resolved = (mode or "").strip().lower()
    if resolved not in DAY_MODES:
        resolved = resolve_day_mode(
            morning_next=morning_next,
            planner_category=planner_category,
            planner_title=planner_title,
            now=now,
            free_override_active=override_on,
            free_after_hm=free_hm,
            day_unlimited=bool(day_unlimited),
        )
    flags = mode_policy_flags(resolved)
    enforce = extension_should_enforce(
        enabled=enabled, locked=locked, morning_next=morning_next, mode=resolved
    )

    watch_flag = flags["block_watch_sites"] if block_watch_sites is None else bool(block_watch_sites)
    porn_flag = flags["block_porn"] if block_porn is None else bool(block_porn)
    social_flag = flags["block_social"] if block_social is None else bool(block_social)
    kw_flag = flags["block_keywords"] if block_keywords is None else bool(block_keywords)
    other_flag = flags["block_other"] if block_other is None else bool(block_other)
    strict = bool(flags["strict_allowlist"])

    redir = resolve_browser_redirect(
        morning_next=morning_next,
        locked=locked,
        enabled=enabled,
        mode=resolved,
        bible_url=bible_url,
        plan_url=plan_url,
    )
    if not enforce:
        redir = {
            **redir,
            "redirect_url": None,
            "redirect_reason": None,
        }

    allow = allow_domains_for_mode(resolved)
    # Errands/shopping daytime: stay study (YouTube blocked) but allow free-life domains.
    allow_free_life = resolved == "free"
    if (
        resolved == "study"
        and is_errands_block(planner_category, planner_title)
        and not is_evening_free_window(now if now is not None else datetime.now().astimezone(), free_after_hm=free_hm)
        and not override_on
    ):
        allow_free_life = True
        allow = merge_free_life_domains(allow)
    elif resolved == "free":
        allow_free_life = True
        # allow_domains_for_mode already merged FREE_LIFE for free
        allow = merge_free_life_domains(allow)

    ov_until = free_override_until() if override_on else None
    from backend.behavior.browser_catalog import catalog_payload

    browsers = catalog_payload()

    return {
        "mode": resolved,
        "mode_label": mode_label(resolved),
        "enforce": enforce,
        "block_other": other_flag and enforce,
        "strict_allowlist": strict and enforce,
        "block_watch_sites": watch_flag and enforce,
        # Distractions always filtered — never tied to Armed/enforce (FREE still blocks).
        "block_porn": porn_flag,
        "block_social": social_flag and enforce,
        "block_keywords": kw_flag,
        "morning_next": (morning_next or "open").strip().lower(),
        "daytime_default": "study",
        "free_after": free_hm,
        "free_override_active": override_on,
        "free_override_until": ov_until.isoformat() if ov_until else None,
        "day_unlimited": bool(day_unlimited),
        "allow_free_life": allow_free_life,
        "free_life_allow_domains": list(FREE_LIFE_ALLOW_DOMAINS),
        "note": (
            "Study browsing = Microsoft Edge + SelfTracker only. "
            "Other browsers and browser installers soft-lock while enforcing. "
            "Study mode allows Scaler/Colab/GitHub — it does not auto-open them. "
            "YouTube/Netflix blocked in bible/planning/study. Free when daily "
            "focus goal is met (day_unlimited), explicit break/leisure blocks, "
            "after free_after, or tray Free time (PIN). "
            "Personal/meal/gym blocks stay study (no YouTube) until goal is met. "
            "Shopping/errands blocks get free-life sites (Amazon etc.) without unlocking YouTube."
        ),
        "allow_domains": allow,
        "localhost_path_prefixes": list(STRICT_LOCALHOST_PATH_PREFIXES) if strict else [],
        "watch_domains": list(DEFAULT_WATCH_DOMAINS),
        "porn_domains": list(DEFAULT_PORN_DOMAINS),
        "porn_suffixes": list(DEFAULT_PORN_SUFFIXES),
        "social_domains": list(DEFAULT_SOCIAL_DOMAINS),
        "block_keywords_list": list(DEFAULT_BLOCK_KEYWORDS),
        "bible_url": redir["bible_url"],
        "plan_url": redir["plan_url"],
        "redirect_url": redir["redirect_url"],
        "redirect_reason": redir["redirect_reason"],
        "nsfw_screen": {
            "desktop_tracker": True,
            "continuous_video_gpu": False,
            "interval_s_default": 60,
            "note": (
                "Occasional CPU NSFW screenshot scan in desktop tracker when Armed "
                "or day-mode enforce. Default weak heuristic if no nudenet/onnx. "
                "Not continuous GPU video. Keywords here are text-only (~0 cost)."
            ),
        },
        "allowed_browsers": browsers["allowed_browsers"],
        "known_browsers": browsers["known_browsers"],
        "browser_installers": browsers["browser_installers"],
        "intervals": {
            "extension_gate_poll_s": 4,
            "extension_gate_idle_alarm_min": 1,
            "nsfw_screen_s": 60,
            "speak_alert_gap_s": 45,
            "note": (
                "Light routine: keyword = string match on URL/title only; "
                "no DOM crawl; NSFW every ~60s CPU when Armed; no 100ms loops."
            ),
        },
    }
