"""Compact suggested links + plan snapshot for SelfTracker locked.html."""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import quote, urlparse

from sqlalchemy.orm import Session

# Prefer these allowlisted hosts as one-click shortcuts (not the full allowlist).
_PRIORITY_ALLOW_HOSTS: tuple[tuple[str, str], ...] = (
    ("scaler.com", "Scaler"),
    ("colab.research.google.com", "Colab"),
    ("github.com", "GitHub"),
    ("leetcode.com", "LeetCode"),
    ("docs.google.com", "Google Docs"),
    ("drive.google.com", "Drive"),
    ("gemini.google.com", "Gemini"),
    ("stackoverflow.com", "Stack Overflow"),
    ("notion.so", "Notion"),
    ("arxiv.org", "arXiv"),
    ("wikipedia.org", "Wikipedia"),
    ("chatgpt.com", "ChatGPT"),
)

# Map planner title / category tokens → allowlisted host shortcuts.
_GOAL_HOST_HINTS: tuple[tuple[str, str, str], ...] = (
    ("scaler", "scaler.com", "Scaler (plan)"),
    ("colab", "colab.research.google.com", "Colab (plan)"),
    ("github", "github.com", "GitHub (plan)"),
    ("leet", "leetcode.com", "LeetCode (plan)"),
    ("codeforce", "codeforces.com", "Codeforces (plan)"),
    ("notion", "notion.so", "Notion (plan)"),
    ("docs", "docs.google.com", "Docs (plan)"),
    ("drive", "drive.google.com", "Drive (plan)"),
    ("gemini", "gemini.google.com", "Gemini (plan)"),
    ("arxiv", "arxiv.org", "arXiv (plan)"),
    ("coursera", "coursera.org", "Coursera (plan)"),
    ("udemy", "udemy.com", "Udemy (plan)"),
    ("khan", "khanacademy.org", "Khan Academy (plan)"),
)

_URL_RE = re.compile(r"https?://[^\s\)\]\>\"\'\<]+", re.IGNORECASE)
_MD_LINK_RE = re.compile(r"\[([^\]]+)\]\((https?://[^)\s]+)\)", re.IGNORECASE)


def _spa_origin(bible_url: str, plan_url: str) -> str:
    for raw in (bible_url, plan_url):
        try:
            p = urlparse(raw)
            if p.scheme and p.netloc:
                return f"{p.scheme}://{p.netloc}"
        except Exception:
            continue
    return "http://localhost:5173"


def _host_url(host: str) -> str:
    h = host.strip().lower().lstrip(".")
    if h.startswith("www."):
        h = h[4:]
    return f"https://{h}/"


def _dedupe_links(links: list[dict[str, str]], *, limit: int = 14) -> list[dict[str, str]]:
    seen: set[str] = set()
    out: list[dict[str, str]] = []
    for item in links:
        url = str(item.get("url") or "").strip()
        title = str(item.get("title") or "").strip() or url
        source = str(item.get("source") or "other").strip() or "other"
        if not url:
            continue
        key = url.rstrip("/").lower()
        if key in seen:
            continue
        seen.add(key)
        out.append({"title": title[:80], "url": url, "source": source})
        if len(out) >= limit:
            break
    return out


def _links_from_plan(title: str | None, category: str | None, allow: set[str]) -> list[dict[str, str]]:
    hay = f"{title or ''} {category or ''}".lower()
    if not hay.strip():
        return []
    out: list[dict[str, str]] = []
    for token, host, label in _GOAL_HOST_HINTS:
        if token not in hay:
            continue
        # Curated productive hosts from plan titles — always offer.
        # If an allowlist is present and explicitly excludes nothing here, still show
        # (goal hints are a short study set, not free-life domains).
        _ = allow  # reserved for future strict filtering
        out.append({"title": label, "url": _host_url(host), "source": "goal"})
    return out


def _links_from_allow_domains(allow_domains: list[str] | None) -> list[dict[str, str]]:
    allow = {str(d).strip().lower() for d in (allow_domains or []) if d}
    out: list[dict[str, str]] = []
    for host, label in _PRIORITY_ALLOW_HOSTS:
        if host in allow or any(a == host or a.endswith("." + host) for a in allow):
            out.append({"title": label, "url": _host_url(host), "source": "allowlist"})
    return out


def _links_from_recent_notes(db: Session, user_id: int, spa_origin: str, *, limit: int = 3) -> list[dict[str, str]]:
    """Recent lecture notes as CALT deep links + a few embedded http(s) URLs."""
    out: list[dict[str, str]] = []
    try:
        from backend.models.study import LectureNote
        from backend.paths import NOTES_DIR
    except Exception:
        return out

    try:
        rows = (
            db.query(LectureNote)
            .filter(LectureNote.user_id == user_id)
            .order_by(LectureNote.created_at.desc())
            .limit(6)
            .all()
        )
    except Exception:
        return out

    for row in rows:
        rel = (getattr(row, "relative_path", None) or getattr(row, "filename", None) or "").strip()
        if not rel:
            continue
        title = (getattr(row, "title", None) or rel).strip() or rel
        out.append(
            {
                "title": f"Notes · {title}"[:80],
                "url": f"{spa_origin}/lecture-notes?file={quote(rel, safe='/')}",
                "source": "notes",
            }
        )
        if len([x for x in out if x["source"] == "notes"]) >= limit:
            break

    # Embedded URLs from a couple of recent note files (disk).
    embedded: list[dict[str, str]] = []
    for row in rows[:3]:
        rel = (getattr(row, "relative_path", None) or getattr(row, "filename", None) or "").strip()
        if not rel:
            continue
        try:
            path = (NOTES_DIR / rel).resolve()
            if not path.is_file() or not path.is_relative_to(NOTES_DIR.resolve()):
                continue
            text = path.read_text(encoding="utf-8", errors="ignore")[:12000]
        except OSError:
            continue
        for m in _MD_LINK_RE.finditer(text):
            label = (m.group(1) or "").strip() or "Note link"
            url = (m.group(2) or "").strip()
            if url and not url.lower().startswith(("javascript:", "data:")):
                embedded.append({"title": label[:80], "url": url, "source": "notes_link"})
        if not embedded:
            for url in _URL_RE.findall(text)[:4]:
                url = url.rstrip(".,;:!?)")
                try:
                    host = urlparse(url).hostname or ""
                except Exception:
                    continue
                if not host or host in {"localhost", "127.0.0.1"}:
                    continue
                embedded.append({"title": host.replace("www.", ""), "url": url, "source": "notes_link"})
        if len(embedded) >= 4:
            break
    out.extend(embedded[:4])
    return out


def build_locked_screen_extras(
    db: Session,
    user_id: int,
    *,
    bible_url: str,
    plan_url: str,
    allow_domains: list[str] | None,
    planner_title: str | None = None,
    planner_category: str | None = None,
    planner_minutes_left: int | None = None,
    morning_next: str = "open",
) -> dict[str, Any]:
    """Small payload for locked.html — stats already live on the gate root."""
    spa = _spa_origin(bible_url, plan_url)
    allow_set = {str(d).strip().lower() for d in (allow_domains or []) if d}

    links: list[dict[str, str]] = [
        {"title": "Bible reader", "url": bible_url, "source": "calt"},
        {"title": "Today's plan", "url": plan_url, "source": "calt"},
        {"title": "Lecture notes", "url": f"{spa}/lecture-notes", "source": "calt"},
        {"title": "Review hub", "url": f"{spa}/review", "source": "calt"},
    ]
    # morning_next reserved for future CTA reordering (bible/plan first already).
    _ = (morning_next or "open").lower()
    links.extend(_links_from_plan(planner_title, planner_category, allow_set))
    links.extend(_links_from_allow_domains(list(allow_set)))
    try:
        links.extend(_links_from_recent_notes(db, user_id, spa))
    except Exception:
        pass

    current_block = None
    if planner_title:
        current_block = {
            "title": planner_title,
            "category": planner_category or "",
            "minutes_left": int(planner_minutes_left) if planner_minutes_left is not None else None,
        }

    return {
        "suggested_links": _dedupe_links(links, limit=14),
        "current_block": current_block,
    }
