"""Canned Jarvis-style gate alert lines — zero LLM, zero GPU.

Pick randomly (or rotate) from pools. Expand the lists anytime.
Optional override file: ``data/voice_agent/block_lines.json``
  { "porn_or_keyword_block": ["…", …], … }

Broader ritual / morning / stats lines live in ``dialogues.py``
(+ optional ``data/voice_agent/dialogues.json``).

Event kinds (canonical):
  morning_bible_required, morning_plan_required, porn_or_keyword_block,
  watch_site_block, unauthorized_browser, nsfw_screen, generic_rule_break

Legacy aliases (porn, keyword, watch, morning_bible, …) map into these.
"""

from __future__ import annotations

import json
import logging
import random
from pathlib import Path
from typing import Any

log = logging.getLogger("calt.block_dialogues")

_ROOT = Path(__file__).resolve().parent.parent.parent.parent
_OVERRIDE_PATH = _ROOT / "data" / "voice_agent" / "block_lines.json"

# --- Built-in pools (Jarvis / butler tone, short) --------------------------------

MORNING_BIBLE_REQUIRED: tuple[str, ...] = (
    "Read today's chapter first.",
    "Bible first, sir. Then we proceed.",
    "Today's chapter is waiting. Shall we?",
    "Morning protocol: one chapter before the open web.",
    "Not yet. Finish the reading, then continue.",
    "The gate asks for Scripture before distraction.",
    "Chapter first. Games and feeds can wait.",
    "A quiet page of the Good Book, then the day.",
    "Unlock begins with today's assigned chapter.",
    "Sir — Bible before browser rabbit holes.",
)

MORNING_PLAN_REQUIRED: tuple[str, ...] = (
    "Confirm your morning plan first.",
    "Plan and goals next. Then we open the day.",
    "Productivity check-in is still pending.",
    "Confirm today's blocks before wandering off.",
    "The morning plan is not confirmed yet.",
    "Goals first. Then freer browsing.",
    "Sir, the planner still needs your nod.",
    "Confirm the plan — thirty seconds — then proceed.",
    "Day unlock: Bible done; plan confirmation remains.",
    "Set the intention. Then the gate softens.",
)

PORN_OR_KEYWORD_BLOCK: tuple[str, ...] = (
    "That site is blocked. Distractions are always off-limits.",
    "Not on the allow list. Redirecting you.",
    "Distractions stay blocked — even in free mode.",
    "Keyword filter tripped. Back to the task.",
    "That material is blocked. Read or study instead.",
    "I am closing that path. Focus, please.",
    "Rule break noted. Productive tabs only.",
    "That content violates the gate. Moving on.",
    "Sir — that corner of the web is sealed.",
    "Blocked. Chapter and coursework remain open.",
    "NSFW text filter engaged. Choose wisely.",
    "Not today. Return to Colab or Scaler.",
)

WATCH_SITE_BLOCK: tuple[str, ...] = (
    "Streaming is blocked until your daily focus goal is met.",
    "YouTube can wait. Hit today's focus target first.",
    "Netflix is offline until the daily goal is done.",
    "Watch sites stay gated in study mode. Back to work.",
    "Entertainment later — after the productive minutes land.",
    "That stream is closed under study rules.",
    "Sir, video sites pause until the daily goal clears.",
    "No binge mode in study. Redirecting.",
    "Streaming denied until focus goal + Bible chapter are done.",
    "The show will still be there after you unlock free mode.",
)

UNAUTHORIZED_BROWSER: tuple[str, ...] = (
    "Unauthorized browser. Use Microsoft Edge only.",
    "Wrong browser. Edge is the only approved shell.",
    "Chrome is not permitted while the gate is armed.",
    "Please switch to Edge.",
    "That browser is outside the allow list.",
    "Sir — Edge only for study browsing.",
    "Unauthorized browser detected. Soft lock engaged.",
    "Rule: Edge only under lock.",
    "Close that browser. Edge is the approved shell.",
    "I will not kill Cursor — but that browser is out of bounds.",
)

BROWSER_INSTALLER: tuple[str, ...] = (
    "Browser installer blocked. Stay on Edge.",
    "Do not install another browser while the gate is on.",
    "Setup for Chrome or Firefox is not allowed right now.",
    "Installer soft-locked. Edge is enough.",
    "Sir, no new browsers under lock. Close the installer.",
)

NSFW_SCREEN: tuple[str, ...] = (
    "Inappropriate screen content detected. Return to study.",
    "Screen check failed. Back to productive work.",
    "That display is not allowed under the gate.",
    "NSFW on screen. Soft lock — choose Bible or study.",
    "I noticed something you should not be viewing.",
    "Screen filter tripped. Redirect your attention.",
    "Sir, the screen scan objects. Change the view.",
    "Occasional check caught this. Correct course.",
    "Visual rule break. Productivity or Scripture.",
    "Not on this display. Close it and refocus.",
)

GENERIC_RULE_BREAK: tuple[str, ...] = (
    "That is blocked. Focus on your goal.",
    "Gate says no. Stay on the path.",
    "Rule break. Soft lock engaged.",
    "Not permitted right now.",
    "Sir, that action is restricted.",
    "Redirecting you to something better.",
    "The gate holds. Read or study.",
    "Discipline first. Distraction later.",
    "Locked in. Choose the productive path.",
    "I am here to keep you honest. Back on task.",
)

POOLS: dict[str, tuple[str, ...]] = {
    "morning_bible_required": MORNING_BIBLE_REQUIRED,
    "morning_plan_required": MORNING_PLAN_REQUIRED,
    "porn_or_keyword_block": PORN_OR_KEYWORD_BLOCK,
    "watch_site_block": WATCH_SITE_BLOCK,
    "unauthorized_browser": UNAUTHORIZED_BROWSER,
    "browser_installer": BROWSER_INSTALLER,
    "nsfw_screen": NSFW_SCREEN,
    "generic_rule_break": GENERIC_RULE_BREAK,
}

# Map extension / tracker kinds → canonical pool keys
KIND_ALIASES: dict[str, str] = {
    "morning_bible": "morning_bible_required",
    "morning_bible_required": "morning_bible_required",
    "bible": "morning_bible_required",
    "morning_plan": "morning_plan_required",
    "morning_plan_required": "morning_plan_required",
    "plan": "morning_plan_required",
    "porn": "porn_or_keyword_block",
    "keyword": "porn_or_keyword_block",
    "porn_or_keyword_block": "porn_or_keyword_block",
    "nsfw": "porn_or_keyword_block",
    "watch": "watch_site_block",
    "watch_site_block": "watch_site_block",
    "social": "watch_site_block",  # social treated like soft distraction speak
    "unauthorized_browser": "unauthorized_browser",
    "browser": "unauthorized_browser",
    "browser_installer": "browser_installer",
    "installer": "browser_installer",
    "nsfw_screen": "nsfw_screen",
    "default": "generic_rule_break",
    "generic": "generic_rule_break",
    "generic_rule_break": "generic_rule_break",
    "armed_distraction": "generic_rule_break",
}

_rotate_idx: dict[str, int] = {}
_override_cache: dict[str, list[str]] | None = None
_override_mtime: float = 0.0


def canonical_kind(kind: str) -> str:
    k = (kind or "default").strip().lower().replace(" ", "_").replace("-", "_")
    return KIND_ALIASES.get(k) or "generic_rule_break"


def _load_overrides() -> dict[str, list[str]]:
    global _override_cache, _override_mtime
    if not _OVERRIDE_PATH.is_file():
        _override_cache = {}
        return {}
    try:
        mtime = _OVERRIDE_PATH.stat().st_mtime
        if _override_cache is not None and mtime == _override_mtime:
            return _override_cache
        raw = json.loads(_OVERRIDE_PATH.read_text(encoding="utf-8"))
        out: dict[str, list[str]] = {}
        if isinstance(raw, dict):
            for key, val in raw.items():
                if isinstance(val, list):
                    lines = [str(x).strip() for x in val if str(x).strip()]
                    if lines:
                        out[canonical_kind(str(key))] = lines
        _override_cache = out
        _override_mtime = mtime
        return out
    except Exception as exc:  # noqa: BLE001
        log.debug("block_lines.json load failed: %s", exc)
        return _override_cache or {}


def lines_for(kind: str) -> list[str]:
    """Resolved line list for a kind (overrides merge on top of built-ins)."""
    key = canonical_kind(kind)
    base = list(POOLS.get(key) or POOLS["generic_rule_break"])
    over = _load_overrides().get(key) or []
    if over:
        return over + base
    return base


def pick_dialogue(
    kind: str,
    *,
    mode: str = "random",
    rng: random.Random | None = None,
) -> str:
    """Return one canned line. mode: random | rotate.

    Never calls the LLM. Empty pools fall back to generic.
    """
    pool = lines_for(kind)
    if not pool:
        pool = list(GENERIC_RULE_BREAK)
    key = canonical_kind(kind)
    if mode == "rotate":
        i = _rotate_idx.get(key, 0) % len(pool)
        _rotate_idx[key] = i + 1
        return pool[i]
    r = rng or random
    return r.choice(pool)


def pool_sizes() -> dict[str, int]:
    return {k: len(lines_for(k)) for k in POOLS}


def reset_rotate_for_tests() -> None:
    global _override_cache, _override_mtime
    _rotate_idx.clear()
    _override_cache = None
    _override_mtime = 0.0
