"""Light browser telemetry from SelfTracker extensions → data_logs JSONL/CSV."""

from __future__ import annotations

import csv
import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from backend.paths import DATA_LOGS_DIR

LOG_DIR = DATA_LOGS_DIR
LOG_DIR.mkdir(exist_ok=True)

_SENSITIVE_QUERY = re.compile(
    r"^(token|access_token|auth|password|passwd|secret|api[_-]?key|session|sid|jwt|code|refresh[_-]?token)$",
    re.I,
)


def sanitize_url(url: str | None, *, domain_only: bool = False, max_len: int = 400) -> str | None:
    if not url or not isinstance(url, str):
        return None
    raw = url.strip()
    if not raw or re.match(r"^(chrome|edge|about|moz-extension|chrome-extension|devtools):", raw, re.I):
        return None
    try:
        parsed = urlparse(raw)
    except Exception:
        return None
    host = (parsed.hostname or "").removeprefix("www.")
    if not host:
        return None
    if domain_only:
        return host
    # Drop fragment + sensitive query tokens
    q = [(k, v) for k, v in parse_qsl(parsed.query, keep_blank_values=True) if not _SENSITIVE_QUERY.match(k)]
    cleaned = urlunparse(
        (parsed.scheme, parsed.netloc, parsed.path, "", urlencode(q), "")
    )
    if len(cleaned) > max_len:
        cleaned = cleaned[:max_len]
    return cleaned


def domain_of(url: str | None) -> str | None:
    if not url:
        return None
    try:
        return (urlparse(url).hostname or "").removeprefix("www.") or None
    except Exception:
        return None


def normalize_telemetry_payload(body: dict[str, Any]) -> dict[str, Any]:
    domain_only = bool(body.get("domain_only"))
    active_in = body.get("active") if isinstance(body.get("active"), dict) else {}
    active_url = sanitize_url(active_in.get("url"), domain_only=domain_only)
    active_domain = active_in.get("domain") or domain_of(active_in.get("url")) or domain_of(active_url)

    open_tabs_out: list[dict[str, Any]] = []
    for tab in body.get("open_tabs") or []:
        if not isinstance(tab, dict):
            continue
        u = sanitize_url(tab.get("url"), domain_only=domain_only)
        d = tab.get("domain") or domain_of(tab.get("url")) or domain_of(u)
        if not d and not u:
            continue
        row: dict[str, Any] = {"domain": d}
        if not domain_only and u:
            row["url"] = u
        if tab.get("title"):
            row["title"] = str(tab["title"])[:120]
        if "active" in tab:
            row["active"] = bool(tab["active"])
        open_tabs_out.append(row)
        if len(open_tabs_out) >= 12:
            break

    history_out: list[dict[str, Any]] = []
    for hit in body.get("recent_history") or []:
        if not isinstance(hit, dict):
            continue
        d = hit.get("domain") or domain_of(hit.get("url"))
        if not d:
            continue
        history_out.append(
            {
                "domain": str(d)[:120],
                "title": str(hit.get("title") or "")[:80] or None,
                "lastVisitTime": hit.get("lastVisitTime"),
            }
        )
        if len(history_out) >= 12:
            break

    tab_count = body.get("tab_count")
    try:
        tab_count_i = int(tab_count) if tab_count is not None else None
    except (TypeError, ValueError):
        tab_count_i = None

    return {
        "received_at": datetime.now(UTC).isoformat(),
        "source": str(body.get("source") or "extension")[:40],
        "browser": str(body.get("browser") or "")[:40] or None,
        "domain_only": domain_only,
        "active_url": active_url,
        "active_title": (str(active_in.get("title") or "")[:160] or None),
        "active_domain": active_domain,
        "tab_count": tab_count_i,
        "open_tabs": open_tabs_out,
        "recent_history": history_out,
        "gate_locked": bool(body.get("gate_locked")) if body.get("gate_locked") is not None else None,
        "gate_enforce": bool(body.get("gate_enforce")) if body.get("gate_enforce") is not None else None,
        "client_ts": body.get("ts"),
    }


def append_telemetry_logs(normalized: dict[str, Any], *, day_str: str | None = None) -> Path:
    """Append one JSONL line + CSV row. Returns JSONL path."""
    day = day_str or datetime.now().astimezone().date().isoformat()
    jsonl_path = LOG_DIR / f"DSC_browser_telemetry_{day}.jsonl"
    csv_path = LOG_DIR / f"DSC_browser_telemetry_{day}.csv"

    with open(jsonl_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(normalized, ensure_ascii=False, default=str) + "\n")

    flat = {
        "received_at": normalized.get("received_at"),
        "browser": normalized.get("browser"),
        "active_domain": normalized.get("active_domain"),
        "active_url": normalized.get("active_url"),
        "active_title": normalized.get("active_title"),
        "tab_count": normalized.get("tab_count"),
        "open_tabs_json": json.dumps(normalized.get("open_tabs") or [], ensure_ascii=False),
        "history_json": json.dumps(normalized.get("recent_history") or [], ensure_ascii=False),
        "gate_locked": normalized.get("gate_locked"),
        "domain_only": normalized.get("domain_only"),
    }
    write_header = not csv_path.exists()
    with open(csv_path, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(flat.keys()))
        if write_header:
            writer.writeheader()
        writer.writerow(flat)

    return jsonl_path
