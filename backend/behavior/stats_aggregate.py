"""Shared aggregation for desktop tracker rows — apps vs browser sites."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from typing import Any

from backend.behavior.category_scores import score_for_category
from backend.behavior.session_key import is_browser_exe, looks_like_domain, normalize_site_from_title
from backend.behavior.tracker_ignore import is_ignored_app


def site_label(exe: str, title: str | None, domain: str | None = None) -> str:
    """Human-readable site/page label for a browser session."""
    if domain and domain.strip():
        return domain.strip()
    if looks_like_domain(exe):
        return exe
    if is_browser_exe(exe):
        site = normalize_site_from_title(title or "")
        if site != "unknown":
            return site
        if title:
            page = title.split(" - ")[0].strip()
            if page:
                return page[:48]
    return exe or "unknown"


@dataclass
class SiteBucket:
    seconds: int = 0
    category: str = "Browser"
    productivity_score: int = 35


@dataclass
class AppBucket:
    seconds: int = 0
    category: str = "Other"
    productivity_score: int = 35
    sites: dict[str, SiteBucket] = field(default_factory=dict)


def _row_fields(
    row: Any,
    scores: dict[str, int],
    policy: dict[str, Any] | None = None,
) -> tuple[str, str | None, str | None, str, int]:
    from backend.behavior.productivity_policy import (
        resolve_category_with_overrides,
        resolve_session_score,
    )

    if isinstance(row, dict):
        exe = row.get("app_name") or row.get("exe") or "unknown"
        title = row.get("window_title") or row.get("title")
        domain = row.get("domain")
        category = row.get("category") or "Other"
        source = row.get("source")
    else:
        exe = row.app_name or "unknown"
        title = row.window_title
        domain = None
        category = row.category or "Other"
        source = getattr(row, "source", None)
    # Extension stores domain in app_name — expose as domain for site bucketing.
    if not domain and (source == "extension" or looks_like_domain(exe)):
        domain = exe
    if policy is not None:
        category = resolve_category_with_overrides(
            category, app_name=exe, window_title=title, policy=policy
        ) or category
        score = resolve_session_score(row, scores, policy)
    else:
        score = score_for_category(category, scores)
    return exe, title, domain, category, score


def aggregate_session_rows(
    rows: list[Any],
    *,
    scores: dict[str, int],
    policy: dict[str, Any] | None = None,
) -> tuple[dict[str, AppBucket], int]:
    """Group tracked rows into app buckets; browsers get nested site buckets."""
    buckets: dict[str, AppBucket] = {}
    total = 0

    for row in rows:
        if isinstance(row, dict):
            start, end = row.get("start_time"), row.get("end_time")
        else:
            start, end = row.start_time, row.end_time
        if not start or not end:
            continue
        dur = max(0, int((end - start).total_seconds()))
        if dur <= 0:
            continue

        exe, title, domain, category, score = _row_fields(row, scores, policy)
        if is_ignored_app(exe, title or ""):
            continue
        total += dur

        if is_browser_exe(exe) or looks_like_domain(exe) or domain:
            # Extension: group under Browser (extension); desktop: under browser exe.
            bucket_key = exe if is_browser_exe(exe) else "Browser (Web)"
            if bucket_key not in buckets:
                buckets[bucket_key] = AppBucket(category=category, productivity_score=score)
            bucket = buckets[bucket_key]
            bucket.seconds += dur
            label = site_label(exe, title, domain)
            if label not in bucket.sites:
                bucket.sites[label] = SiteBucket(category=category, productivity_score=score)
            site = bucket.sites[label]
            site.seconds += dur
            if category and category != "Other":
                site.category = category
                site.productivity_score = score
        else:
            if exe not in buckets:
                buckets[exe] = AppBucket(category=category, productivity_score=score)
            bucket = buckets[exe]
            bucket.seconds += dur
            if category and category != "Other":
                bucket.category = category
                bucket.productivity_score = score

    return buckets, total


def desktop_sessions_payload(buckets: dict[str, AppBucket], *, limit: int = 20) -> list[dict]:
    """Build desktop-stats session list with browser site breakdown."""
    entries: list[dict] = []

    for exe, bucket in buckets.items():
        if bucket.sites:
            sites = [
                {
                    "site": site,
                    "seconds": data.seconds,
                    "category": data.category,
                    "productivity_score": data.productivity_score,
                }
                for site, data in sorted(
                    bucket.sites.items(), key=lambda x: x[1].seconds, reverse=True
                )
            ]
            entries.append({
                "kind": "browser",
                "exe": exe,
                "seconds": bucket.seconds,
                "category": bucket.category,
                "productivity_score": bucket.productivity_score,
                "sites": sites,
            })
        else:
            entries.append({
                "kind": "app",
                "exe": exe,
                "seconds": bucket.seconds,
                "category": bucket.category,
                "productivity_score": bucket.productivity_score,
            })

    entries.sort(key=lambda x: x["seconds"], reverse=True)
    return entries[:limit]


def browser_domains_payload(buckets: dict[str, AppBucket], *, limit: int = 15) -> list[dict]:
    """Flatten browser site buckets for /api/behavior/stats."""
    site_seconds: Counter[str] = Counter()
    site_events: Counter[str] = Counter()
    site_category: dict[str, str] = {}
    site_score: dict[str, int] = {}
    categories: Counter[str] = Counter()

    for _exe, bucket in buckets.items():
        if not bucket.sites:
            continue
        for site, data in bucket.sites.items():
            site_seconds[site] += data.seconds
            site_events[site] += 1
            if site not in site_category:
                site_category[site] = data.category
                site_score[site] = data.productivity_score
            categories[data.category] += data.seconds

    domains = [
        {
            "domain": site,
            "seconds": site_seconds[site],
            "count": site_events[site],
            "category": site_category.get(site, "Other (Browser)"),
            "productivity_score": site_score.get(site, 35),
        }
        for site, _ in site_seconds.most_common(limit)
    ]
    top_categories = [{"category": k, "seconds": v} for k, v in categories.most_common(10)]
    return domains, top_categories, sum(site_events.values())
