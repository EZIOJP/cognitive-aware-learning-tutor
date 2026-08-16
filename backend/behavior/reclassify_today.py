"""Hard reclassify today's tracked sessions so productive minutes match current rules."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from urllib.parse import urlparse

from sqlalchemy.orm import Session

from backend.models.timetable import TrackedSession


def derive_session_category(
    *,
    source: str,
    app_name: str | None,
    window_title: str | None,
    url: str | None = None,
    domain: str | None = None,
    policy: dict | None = None,
) -> tuple[str, str]:
    """Re-derive category from domain/title/url using current classify helpers.

    Returns (category, category_source) where category_source is usually
    ``reclassify_today`` (or ``policy_override`` when policy wins).
    """
    from backend.behavior.domain_classify import classify_browser_title, classify_domain
    from backend.behavior.productivity_policy import resolve_category_with_overrides
    from backend.behavior.session_key import is_browser_exe, looks_like_domain
    from backend.behavior.tracker_classify import classify_app
    from backend.timetable.tracker_bridge import _EXT_CATEGORY_MAP

    app = (app_name or "").strip()
    title = (window_title or "").strip()
    url_s = (url or "").strip()
    domain_s = (domain or "").strip().lower().removeprefix("www.")

    if not domain_s and looks_like_domain(app):
        domain_s = app.lower().removeprefix("www.")
    if not domain_s and url_s:
        try:
            domain_s = (urlparse(url_s).hostname or "").lower().removeprefix("www.")
        except Exception:  # noqa: BLE001
            domain_s = ""

    category: str
    if source == "calt_spa" and not (domain_s or url_s or title):
        category = "Study (Browser)"
    elif domain_s or url_s:
        hay = domain_s or url_s
        category, _ = classify_domain(hay, title or url_s)
    elif source in ("extension", "calt_spa") or is_browser_exe(app):
        if title:
            category, _ = classify_browser_title(title)
        else:
            category = "Other (Browser)"
    else:
        # Desktop apps: classify by exe only — window titles often contain
        # browser chrome / "Cursor" / site names and poison app rules.
        category, _ = classify_app(app, "")

    # Map short extension labels if somehow still present
    if category in _EXT_CATEGORY_MAP:
        category = _EXT_CATEGORY_MAP[category]

    overridden = resolve_category_with_overrides(
        category, app_name=app, window_title=title, policy=policy
    )
    if overridden and overridden != category:
        return overridden, "policy_override"
    return category, "reclassify_today"


_BROWSERISH_CATEGORIES = frozenset(
    {
        "Browser",
        "Other (Browser)",
        "Video Streaming",
        "Video (YouTube)",
        "Live Streaming",
        "Entertainment",
        "Social Media",
        "Social / Forum",
        "Music / Media",
        "Shopping",
        "News",
        "Other",
        "Study (Browser)",
        "Coursework (Browser)",
        "Coding Practice",
        "Research",
        "Tech Reading",
        "Documentation",
        "Reference",
    }
)


def _should_reclassify_row(row: TrackedSession) -> bool:
    """Prefer browser/extension/spa rows; skip stable desktop IDE/Terminal etc."""
    if (row.category_source or "") == "user_override":
        return False
    source = str(row.source or "")
    if source in ("extension", "calt_spa"):
        return True
    app = row.app_name or ""
    from backend.behavior.session_key import is_browser_exe, looks_like_domain

    if is_browser_exe(app) or looks_like_domain(app):
        return True
    # Non-browser desktop: only rewrite generic / browser-ish categories
    return (row.category or "") in _BROWSERISH_CATEGORIES


def _load_browser_url_hints(
    db: Session,
    user_id: int,
    start: datetime,
    end: datetime,
) -> dict:
    """Index browser_event readings for URL/domain hints keyed by session_id / overlap."""
    import json

    from backend.models.hub import Reading, ReadingDefinition

    empty: dict = {"by_sid": {}, "overlaps": []}
    defn = db.query(ReadingDefinition).filter(ReadingDefinition.slug == "browser_event").first()
    if not defn:
        return empty

    # Pad slightly — readings may land just outside session clip
    pad = timedelta(hours=1)
    rows = (
        db.query(Reading)
        .filter(
            Reading.user_id == user_id,
            Reading.definition_id == defn.id,
            Reading.recorded_at >= start - pad,
            Reading.recorded_at < end + pad,
        )
        .all()
    )

    by_sid: dict[str, dict[str, str]] = {}
    overlaps: list[tuple[float, float, str, str, str]] = []

    for row in rows:
        try:
            payload = json.loads(row.value_json) if row.value_json else {}
        except (TypeError, json.JSONDecodeError):
            continue
        if not isinstance(payload, dict):
            continue
        if payload.get("type") and payload.get("type") != "SESSION_END":
            if not (payload.get("url") or payload.get("domain")):
                continue

        url = str(payload.get("url") or "").strip()
        domain = str(payload.get("domain") or "").strip().lower()
        title = str(payload.get("title") or payload.get("window_title") or "").strip()
        if not url and not domain:
            continue
        if not domain and url:
            try:
                domain = (urlparse(url).hostname or "").lower().removeprefix("www.")
            except Exception:  # noqa: BLE001
                domain = ""

        sid = str(payload.get("session_id") or "").strip()
        if sid and (url or domain):
            prev = by_sid.get(sid)
            if prev is None or (url and not prev.get("url")):
                by_sid[sid] = {"url": url, "domain": domain, "title": title}

        try:
            ts = float(payload.get("timestamp") or 0)
            te = float(payload.get("end_timestamp") or ts)
        except (TypeError, ValueError):
            if row.recorded_at is not None:
                ts = row.recorded_at.timestamp() * 1000
                te = ts
            else:
                continue
        if te < ts:
            te = ts
        overlaps.append((ts, te, domain, url, title))

    return {"by_sid": by_sid, "overlaps": overlaps}


def _hint_for_session(
    row: TrackedSession,
    index: dict,
) -> tuple[str | None, str | None, str | None]:
    by_sid: dict = index.get("by_sid") or {}
    overlaps: list = index.get("overlaps") or []

    hit = by_sid.get(row.session_id)
    if hit:
        return hit.get("url") or None, hit.get("domain") or None, hit.get("title") or None

    if not row.start_time or not row.end_time:
        return None, None, None

    a = row.start_time
    b = row.end_time
    if a.tzinfo is None:
        a = a.replace(tzinfo=UTC)
    if b.tzinfo is None:
        b = b.replace(tzinfo=UTC)
    a_ms = a.timestamp() * 1000
    b_ms = b.timestamp() * 1000

    app = (row.app_name or "").strip().lower()
    best = None
    best_overlap = 0.0
    for ts, te, domain, url, title in overlaps:
        ov = min(b_ms, te) - max(a_ms, ts)
        if ov <= 0:
            continue
        # Prefer domain match to app_name when extension stored domain
        if app and domain and app != domain and app not in domain and domain not in app:
            # still allow if title similar / large overlap
            if ov < 5_000:
                continue
        if ov > best_overlap:
            best_overlap = ov
            best = (url or None, domain or None, title or None)
    if best:
        return best
    return None, None, None


def reclassify_today(
    db: Session,
    user_id: int,
    *,
    day: date | None = None,
    commit: bool = True,
    null_sleep_overlap: bool = True,
) -> dict:
    """In-place category rewrite for one local calendar day.

    Skips ``user_override`` rows. Does not delete sessions.
    When ``null_sleep_overlap``, stamps PC sessions overlapping sleep as
    non-productive (``sleep_overwrite``).
    """
    from backend.behavior.distraction_gate import compute_distraction_gate
    from backend.behavior.productivity_policy import load_policy_dict
    from backend.planner.service import local_day_bounds_utc, local_tz
    from backend.wearables.sleep_window import stamp_sessions_nonproductive_during_sleep

    day_date = day or datetime.now(local_tz()).date()
    start, end = local_day_bounds_utc(day_date)
    policy = load_policy_dict(db, user_id)

    before_gate = compute_distraction_gate(db, user_id)
    before_productive = int(before_gate.get("productive_minutes") or 0)

    rows = (
        db.query(TrackedSession)
        .filter(
            TrackedSession.user_id == user_id,
            TrackedSession.source.in_(("desktop_tracker", "extension", "calt_spa")),
            TrackedSession.start_time < end,
            TrackedSession.end_time > start,
        )
        .all()
    )

    url_index = _load_browser_url_hints(db, user_id, start, end)

    updated = 0
    samples: list[dict] = []
    scanned = 0

    for row in rows:
        scanned += 1
        if not _should_reclassify_row(row):
            continue

        url, domain, hint_title = _hint_for_session(row, url_index)
        title = row.window_title or hint_title
        new_cat, new_src = derive_session_category(
            source=str(row.source or ""),
            app_name=row.app_name,
            window_title=title,
            url=url,
            domain=domain,
            policy=policy,
        )
        old_cat = row.category or ""
        if new_cat == old_cat:
            if (row.category_source or "") != new_src:
                row.category_source = new_src
                updated += 1
            continue

        if len(samples) < 25:
            samples.append(
                {
                    "session_id": row.session_id,
                    "from": old_cat,
                    "to": new_cat,
                    "app_name": row.app_name,
                    "window_title": (row.window_title or "")[:80],
                    "source": row.source,
                }
            )
        row.category_before_llm = row.category_before_llm or old_cat
        row.category = new_cat
        row.category_source = new_src
        updated += 1

    sleep_stamp: dict = {"stamped": 0}
    if null_sleep_overlap:
        # Flush category edits first so stamp sees current rows
        db.flush()
        sleep_stamp = stamp_sessions_nonproductive_during_sleep(
            db, user_id, day=day_date, commit=False
        )

    if commit:
        db.commit()
    else:
        db.flush()

    after_gate = compute_distraction_gate(db, user_id)
    after_productive = int(after_gate.get("productive_minutes") or 0)

    return {
        "day": day_date.isoformat(),
        "user_id": user_id,
        "scanned": scanned,
        "updated": updated,
        "samples": samples,
        "sleep_overwrite": sleep_stamp,
        "productive_minutes_before": before_productive,
        "productive_minutes_after": after_productive,
    }
