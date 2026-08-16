"""Structured canned dialogue bank for Jarvis — zero LLM.

Categories cover morning ritual, productivity, tasks, gate blocks, and chat.
Gate block pools live in ``block_dialogues`` and are merged here.

Optional overrides: ``data/voice_agent/dialogues.json``
  { "morning_greet": ["…", …], "productivity_stats_brief": ["Focus {focus_min}m…"], … }

Legacy gate overrides still load from ``data/voice_agent/block_lines.json``.
"""

from __future__ import annotations

import json
import logging
import random
from datetime import datetime
from pathlib import Path
from typing import Any

from backend.behavior.voice_agent import block_dialogues as _blocks
from backend.planner.service import local_tz

log = logging.getLogger("calt.dialogues")

_ROOT = Path(__file__).resolve().parent.parent.parent.parent
_OVERRIDE_PATH = _ROOT / "data" / "voice_agent" / "dialogues.json"

# --- Built-in pools (concise butler, dry wit, "sir" sparingly) ---------------------

MORNING_GREET: tuple[str, ...] = (
    "Good morning. Shall we set the day?",
    "Morning. Goals first, then the open web.",
    "Ah — you're up. Brief on deck.",
    "Good morning. Ready when you are.",
    "Day starts here. I'll keep it short.",
    "Morning, sir. Ritual before rabbit holes.",
    "Hello. Let's see what needs finishing.",
    "Rise and focus. I have a quick brief.",
    "Good morning. Bible, plan, then freedom.",
    "You're here. Let's unlock the day properly.",
    "Morning check-in. Nothing theatrical.",
    "Good morning. Two minutes of order, then work.",
)

MORNING_GREET_AFTERNOON: tuple[str, ...] = (
    "Good afternoon. Catching the day mid-stream.",
    "Afternoon. Still time to lock in the plan.",
    "Hello again. Brief, then back to it.",
    "Afternoon check-in — keep it crisp.",
    "You're back. Shall we review the board?",
    "Good afternoon. Goals still matter after lunch.",
    "Midday hello. What's left on the list?",
    "Afternoon. I'll keep the speech short.",
    "Still daylight. Let's tidy priorities.",
    "Hello. A quick status, then silence.",
)

MORNING_BIBLE_NUDGE: tuple[str, ...] = (
    "Today's chapter is still waiting.",
    "Bible first — then we open the day.",
    "One chapter unlocks the morning gate.",
    "Scripture before feeds. Shall we?",
    "The assigned chapter is unfinished.",
    "Quiet page first. Distraction later.",
    "Morning protocol: chapter, then plan.",
    "Read today's portion when you can.",
    "Gate holds until the chapter is done.",
    "A short reading — then productivity.",
    "Sir — Bible before browser sprawl.",
    "Chapter first. I'll wait.",
)

BIBLE_DONE_PRAISE: tuple[str, ...] = (
    "Chapter done. Well handled.",
    "Reading complete. Plan is next.",
    "Good — Scripture's logged for today.",
    "Bible goal met. Onward.",
    "That's today's chapter. Steady work.",
    "Done. The morning gate softens a notch.",
    "Chapter marked. Confirm the plan when ready.",
    "Nicely finished. Goals are next.",
    "Reading complete. I'll keep the praise brief.",
    "Solid. Plan confirmation unlocks the rest.",
    "Chapter secured. Shall we confirm today's blocks?",
    "Well read. Productivity step awaits.",
)

MORNING_PLAN_BRIEF: tuple[str, ...] = (
    "Next: glance at today's blocks and confirm.",
    "Plan step — review goals, then nod yes.",
    "Confirm the morning plan to open the day.",
    "Blocks are waiting for your confirmation.",
    "Thirty seconds on the planner, then we proceed.",
    "Set the intention. Confirm when it looks right.",
    "Plan and goals next — compulsory, blessedly short.",
    "Review today's schedule, then confirm.",
    "The gate wants a confirmed plan. Almost there.",
    "Goals check-in. Confirm and you're free to work.",
    "Planner needs your nod before freer browsing.",
    "Confirm today's plan — then the open web.",
)

PLAN_AUTO_DRAFTED: tuple[str, ...] = (
    "I've drafted today's plan from your routines. Confirm when it looks right.",
    "Plan draft is ready — routines and a couple of focus blocks. Please confirm.",
    "Today's schedule is pre-filled. Glance over it, then confirm.",
    "Auto-plan ready. Review the blocks, then confirm to unlock.",
    "I've sketched today's plan. Confirm when you're happy with it.",
    "Draft on the Productivity page. Confirm keeps the morning gate honest.",
    "Routines applied and focus blocks seeded. Confirm when ready.",
    "Today's plan is drafted — not confirmed yet. Your nod still matters.",
)

PLAN_EXISTS_ASK: tuple[str, ...] = (
    "Blocks are already on today. Add more, or confirm as-is?",
    "You already have a plan. Want me to add more blocks, or is it fine?",
    "Calendar has blocks. Say add more — or confirm as fine.",
    "Plan exists. Add more gaps, or confirm as-is on Productivity.",
    "Blocks already scheduled. Add more, or fine as-is?",
)

PLAN_CONFIRM_PROMPT: tuple[str, ...] = (
    "Does today's plan look right? Confirm when ready.",
    "Nod to the plan and we unlock.",
    "Confirm if those blocks match your intent.",
    "Ready to confirm today's plan?",
    "One confirm click. Then open.",
    "If the schedule fits, confirm it.",
    "Shall I wait for plan confirmation?",
    "Confirm goals — then distraction softens.",
    "Plan look sane? Confirm and proceed.",
    "Your confirmation unlocks the morning gate.",
)

PLAN_DONE_PRAISE: tuple[str, ...] = (
    "Plan confirmed. Day is open.",
    "Confirmed. Work freely — I'll still mind the gate.",
    "Goals locked in. Good.",
    "Morning unlock complete. Carry on.",
    "Plan done. Stay honest with the blocks.",
    "Confirmed. The ritual is finished.",
    "Day open. Don't squander the unlock.",
    "Nicely done. Focus when it counts.",
    "Plan secured. I'll keep soft locks honest.",
    "Unlocked. Productive paths preferred.",
    "That's the morning chain. Get to it.",
    "Confirmed, sir. Brief praise, then silence.",
)

# Soft only — after plan; uses {due} placeholder when due cards exist.
DAILY_PRACTICE_NUDGE: tuple[str, ...] = (
    "Daily practice when you're ready — {due} due in Review Hub.",
    "Optional: clear {due} review cards. No lock — just a nudge.",
    "Plan's done. Soft hint: {due} cards waiting if you want them.",
    "Review Hub has {due} due. Vocab, math, notes — your call.",
    "A short practice stack is ready — {due} items. Optional.",
    "Whenever you like: daily practice, {due} due.",
    "Retention tip only — {due} cards. Soft-land stays open.",
    "After planning, a quick review helps. {due} waiting.",
)

TASK_NUDGE: tuple[str, ...] = (
    "A task is still open. Worth a push?",
    "Something unfinished on the board.",
    "One more block before you drift.",
    "Tasks don't finish themselves. Gently.",
    "Back to the list when you're ready.",
    "Pending work noticed. No lecture.",
    "Shall we knock out one open item?",
    "Focus window — pick a task.",
    "Incomplete items remain. Your call.",
    "Nudge only: there's work waiting.",
)

TASK_COMPLETE: tuple[str, ...] = (
    "Task done. Marked.",
    "Finished. Good tempo.",
    "Another one down.",
    "Complete. Next when you want it.",
    "Checked off. Steady.",
    "Done. I'll keep the applause short.",
    "Task cleared. Onward.",
    "Nice close on that one.",
    "Completed. Momentum helps.",
    "That's one less open loop.",
)

PRODUCTIVITY_STATS_BRIEF: tuple[str, ...] = (
    "Yesterday: {focus_min}m focus, {distracted_min}m drift, {blocks} sessions logged.",
    "Quick stats — focus {focus_min} minutes; distracted about {distracted_min}; {blocks} blocks of activity.",
    "Last day: {focus_min}m on-task, {distracted_min}m elsewhere, {blocks} sessions.",
    "Rollup: {focus_min} focus minutes, {distracted_min} low-score, {blocks} slices.",
    "Numbers — focus {focus_min}, drift {distracted_min}, activity chunks {blocks}.",
    "Productivity sketch: {focus_min}m focused vs {distracted_min}m not; {blocks} sessions.",
    "From the log: {focus_min} minutes productive, {distracted_min} less so, {blocks} entries.",
    "Brief scoreboard — {focus_min}m focus / {distracted_min}m drift / {blocks} sessions.",
)

PLAN_FROM_YESTERDAY: tuple[str, ...] = (
    "Yesterday left {focus_min}m of real focus. Plan today around that energy.",
    "With {focus_min} focused minutes yesterday, keep today's blocks realistic.",
    "Prior day: {focus_min}m focus. Maybe fewer ambitious blocks today.",
    "Build today's plan from yesterday's {focus_min} focused minutes — not wishful thinking.",
    "You logged {focus_min}m on-task yesterday. Carry the wins forward.",
    "Yesterday's focus was {focus_min} minutes. Protect a similar window today.",
    "From last productivity: {focus_min}m focus, {distracted_min}m drift. Adjust the plan.",
    "Plan hint — yesterday focus {focus_min}m across {blocks} sessions. Keep it honest.",
)

IDLE_CHECKIN: tuple[str, ...] = (
    "Still here. Need anything?",
    "Checking in — brief only.",
    "Hello again. Say the word.",
    "I'm around. No wake word required.",
    "Quiet check-in. Carry on if busy.",
    "Present. Commands or silence — your choice.",
    "Just noting you're in chat. Carry on.",
    "Standing by.",
)

GOODBYE: tuple[str, ...] = (
    "Understood. I'll be quiet.",
    "Later. Gate still watches.",
    "Closing the chat voice. Tracker stays.",
    "Goodbye for now.",
    "Signing off speech. Work continues.",
    "Quiet mode. Call when needed.",
    "Farewell — briefly.",
    "Done speaking. Stay on task.",
)

SESSION_END: tuple[str, ...] = (
    "Session closed.",
    "Voice session ended.",
    "That's the turn. Resources released.",
    "Done. Mic idle again.",
    "Turn complete.",
    "Session finished. No models left warm on purpose.",
    "Ended. Hotkey still works if enabled.",
    "Closed cleanly.",
)

MODE_BIBLE: tuple[str, ...] = (
    "Bible mode. Stay on the chapter — the open web can wait.",
    "Morning Bible gate. Finish the reading first.",
    "Strict mode: Bible and CALT only until the chapter is done.",
    "Chapter first. Everything else is blocked for now.",
)

MODE_PLANNING: tuple[str, ...] = (
    "Planning mode. Confirm today's plan — sites are locked to CALT.",
    "Plan window. Stay on Productivity until you confirm.",
    "Strict planning. Localhost bible and plan pages only.",
    "Set the day, then the web opens for study.",
)

MODE_STUDY: tuple[str, ...] = (
    "Study mode. Goal sites only — Scaler, Colab, docs, GitHub. YouTube stays blocked until the daily goal.",
    "Focus block. Open Scaler if that is today's goal — entertainment unlocks after focus minutes.",
    "Study gate on. Scaler is allowed; nothing auto-opens it. Stay on productive domains.",
    "Deep work. YouTube and social are blocked until today's focus goal is met.",
)

MODE_FREE: tuple[str, ...] = (
    "Free mode — daily goal met. YouTube is fine; distractions stay blocked.",
    "Day unlocked. Watch sites open; distractions and NSFW keywords stay filtered.",
    "Leisure mode. Entertainment allowed — distraction filter still on.",
    "Free browsing after the goal. Distractions remain sealed.",
)

STACK_WEB_DOWN: tuple[str, ...] = (
    "Web UI is down. Start the CALT stack from here — I'll open the page when Vite is up.",
    "Frontend offline. Use Start CALT stack; blank tabs help nobody.",
    "Vite is not answering. Start the stack, then we redirect.",
    "Sir — the Web UI is down. Start stack from the tracker.",
)

STACK_API_DOWN: tuple[str, ...] = (
    "API is down. Gate data may be stale until FastAPI is back.",
    "Backend offline on port 8000. Start CALT stack when you can.",
    "API silent. Pages may load empty until the stack is up.",
)

STACK_BOTH_DOWN: tuple[str, ...] = (
    "API and Web are down. Start CALT stack — I'll wait, then open the page.",
    "Full stack offline. Start from the tracker; no blank browsers.",
    "Nothing on 8000 or 5173. Launch the stack here.",
)

STACK_STARTING: tuple[str, ...] = (
    "Starting CALT stack. Hang on while API and Vite come up.",
    "Launching run.bat. I'll open the page when ready.",
    "Stack starting. One moment.",
)

STACK_READY: tuple[str, ...] = (
    "Stack is ready. Opening the page.",
    "Web UI is up. Redirecting now.",
    "CALT is online. Here we go.",
)

GAME_BLOCKED: tuple[str, ...] = (
    "Game blocked. Finish today's chapter or study goal first.",
    "That game is locked. Bible or study unlocks the day.",
    "Hard-block holds. Read or hit the study goal.",
    "Sir — games stay closed until the gate opens.",
)

# Map category → pool (gate kinds added in _all_pools)
_CUSTOM_POOLS: dict[str, tuple[str, ...]] = {
    "morning_greet": MORNING_GREET,
    "morning_greet_afternoon": MORNING_GREET_AFTERNOON,
    "morning_bible_nudge": MORNING_BIBLE_NUDGE,
    "bible_done_praise": BIBLE_DONE_PRAISE,
    "morning_plan_brief": MORNING_PLAN_BRIEF,
    "plan_auto_drafted": PLAN_AUTO_DRAFTED,
    "plan_exists_ask": PLAN_EXISTS_ASK,
    "plan_confirm_prompt": PLAN_CONFIRM_PROMPT,
    "plan_done_praise": PLAN_DONE_PRAISE,
    "daily_practice_nudge": DAILY_PRACTICE_NUDGE,
    "task_nudge": TASK_NUDGE,
    "task_complete": TASK_COMPLETE,
    "productivity_stats_brief": PRODUCTIVITY_STATS_BRIEF,
    "plan_from_yesterday": PLAN_FROM_YESTERDAY,
    "idle_checkin": IDLE_CHECKIN,
    "goodbye": GOODBYE,
    "session_end": SESSION_END,
    "mode_bible": MODE_BIBLE,
    "mode_planning": MODE_PLANNING,
    "mode_study": MODE_STUDY,
    "mode_free": MODE_FREE,
    "stack_web_down": STACK_WEB_DOWN,
    "stack_api_down": STACK_API_DOWN,
    "stack_both_down": STACK_BOTH_DOWN,
    "stack_starting": STACK_STARTING,
    "stack_ready": STACK_READY,
    "game_blocked": GAME_BLOCKED,
}

# Friendly aliases → category keys
CATEGORY_ALIASES: dict[str, str] = {
    "greet": "morning_greet",
    "morning": "morning_greet",
    "bible_nudge": "morning_bible_nudge",
    "bible_done": "bible_done_praise",
    "plan_brief": "morning_plan_brief",
    "plan_auto_drafted": "plan_auto_drafted",
    "auto_plan": "plan_auto_drafted",
    "plan_exists_ask": "plan_exists_ask",
    "plan_exists": "plan_exists_ask",
    "plan_confirm": "plan_confirm_prompt",
    "plan_done": "plan_done_praise",
    "daily_practice": "daily_practice_nudge",
    "practice_nudge": "daily_practice_nudge",
    "stats": "productivity_stats_brief",
    "yesterday": "plan_from_yesterday",
    "idle": "idle_checkin",
    "bye": "goodbye",
    "mode_bible": "mode_bible",
    "mode_planning": "mode_planning",
    "mode_study": "mode_study",
    "mode_free": "mode_free",
    "bible_mode": "mode_bible",
    "planning_mode": "mode_planning",
    "study_mode": "mode_study",
    "free_mode": "mode_free",
    "web_down": "stack_web_down",
    "api_down": "stack_api_down",
    "stack_down": "stack_both_down",
    "stack_starting": "stack_starting",
    "stack_ready": "stack_ready",
    "game_blocked": "game_blocked",
    "game_block": "game_blocked",
    # Gate aliases (block_dialogues)
    **_blocks.KIND_ALIASES,
}

_DEFAULT_FMT: dict[str, str] = {
    "focus_min": "0",
    "distracted_min": "0",
    "blocks": "0",
}

_rotate_idx: dict[str, int] = {}
_override_cache: dict[str, list[str]] | None = None
_override_mtime: float = 0.0


def _hour_now() -> int:
    return datetime.now(local_tz()).hour


def canonical_category(category: str) -> str:
    c = (category or "").strip().lower().replace(" ", "_").replace("-", "_")
    if c in CATEGORY_ALIASES:
        return CATEGORY_ALIASES[c]
    if c in _CUSTOM_POOLS:
        return c
    if c in _blocks.POOLS:
        return c
    # gate fallback via block_dialogues
    return _blocks.canonical_kind(c)


def _all_builtin() -> dict[str, tuple[str, ...]]:
    out = dict(_CUSTOM_POOLS)
    out.update(_blocks.POOLS)
    return out


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
                        out[canonical_category(str(key))] = lines
        _override_cache = out
        _override_mtime = mtime
        return out
    except Exception as exc:  # noqa: BLE001
        log.debug("dialogues.json load failed: %s", exc)
        return _override_cache or {}


def lines_for(category: str) -> list[str]:
    """Resolved lines for a category (JSON overrides prepend built-ins)."""
    key = canonical_category(category)
    # Time-aware greet: afternoon pool after noon when asking morning_greet
    if key == "morning_greet" and _hour_now() >= 12:
        base = list(_CUSTOM_POOLS.get("morning_greet_afternoon") or MORNING_GREET_AFTERNOON)
    else:
        pools = _all_builtin()
        base = list(pools.get(key) or ())
        if not base:
            # fall back through block_dialogues (includes generic)
            base = _blocks.lines_for(key)
    over = _load_overrides().get(key) or []
    # Also merge legacy block_lines.json for gate kinds
    if key in _blocks.POOLS:
        try:
            over = (_blocks._load_overrides().get(key) or []) + over  # noqa: SLF001
        except Exception:  # noqa: BLE001
            pass
    if over:
        return over + base
    return base


def _safe_format(template: str, fmt: dict[str, Any]) -> str:
    merged = {**_DEFAULT_FMT, **{k: str(v) for k, v in fmt.items()}}

    class _Map(dict):
        def __missing__(self, key: str) -> str:  # type: ignore[override]
            return merged.get(key, _DEFAULT_FMT.get(key, ""))

    try:
        return template.format_map(_Map(**merged))
    except Exception:  # noqa: BLE001
        return template


def pick(
    category: str,
    *,
    mode: str = "random",
    rng: random.Random | None = None,
    **fmt: Any,
) -> str:
    """Return one canned line; fill ``{focus_min}`` etc. when present. Never LLM."""
    pool = lines_for(category)
    if not pool:
        pool = list(_blocks.GENERIC_RULE_BREAK)
    key = canonical_category(category)
    if mode == "rotate":
        i = _rotate_idx.get(key, 0) % len(pool)
        _rotate_idx[key] = i + 1
        line = pool[i]
    else:
        r = rng or random
        line = r.choice(pool)
    return _safe_format(line, fmt)


def speak(
    category: str,
    *,
    force: bool = False,
    mode: str = "random",
    **fmt: Any,
) -> str:
    """Pick a line and speak via rate-limited gate alert TTS. Returns the line."""
    line = pick(category, mode=mode, **fmt)
    try:
        from backend.behavior.gate_alerts import speak_alert

        speak_alert(line, force=force)
    except Exception as exc:  # noqa: BLE001
        log.debug("dialogue speak failed: %s", exc)
    return line


def pool_sizes() -> dict[str, int]:
    keys = sorted(set(_CUSTOM_POOLS) | set(_blocks.POOLS))
    return {k: len(lines_for(k)) for k in keys}


def all_categories() -> list[str]:
    return sorted(set(_CUSTOM_POOLS) | set(_blocks.POOLS))


def reset_for_tests() -> None:
    global _override_cache, _override_mtime
    _rotate_idx.clear()
    _override_cache = None
    _override_mtime = 0.0
    _blocks.reset_rotate_for_tests()
