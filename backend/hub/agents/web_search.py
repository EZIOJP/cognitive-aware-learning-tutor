"""Optional web search via Tavily API (search → chat enrichment)."""

from __future__ import annotations

import logging
from typing import Any

import httpx

log = logging.getLogger(__name__)


def tavily_search(query: str, *, max_results: int = 5) -> list[dict[str, Any]]:
    from backend.config import get_settings

    key = (get_settings().tavily_api_key or "").strip()
    if not key:
        return []
    try:
        with httpx.Client(timeout=15.0) as client:
            res = client.post(
                "https://api.tavily.com/search",
                json={"api_key": key, "query": query, "max_results": max_results},
            )
            res.raise_for_status()
            data = res.json()
            return list(data.get("results") or [])
    except Exception as exc:
        log.warning("Tavily search failed: %s", exc)
        return []


def format_search_context(results: list[dict[str, Any]]) -> str:
    if not results:
        return ""
    lines: list[str] = []
    for i, hit in enumerate(results[:5], 1):
        title = (hit.get("title") or "").strip()
        content = (hit.get("content") or hit.get("snippet") or "").strip()
        url = (hit.get("url") or "").strip()
        lines.append(f"[{i}] {title}\n{content[:600]}\nSource: {url}")
    return "\n\n".join(lines)
