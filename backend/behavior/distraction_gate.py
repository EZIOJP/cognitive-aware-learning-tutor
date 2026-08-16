"""Distraction hard-block until daily productive goal (games + custom exes)."""

from __future__ import annotations

import logging
import os
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import Session

log = logging.getLogger("calt.distraction_gate")

# Seed list — common launchers / clients / desktop distractions
# (user can extend via hard_block_exes). Browsers are never seeded here.
DEFAULT_HARD_BLOCK_EXES: list[str] = [
    # Steam / Epic / Riot / GOG / Battle.net
    "steam.exe",
    "steamwebhelper.exe",
    "steamservice.exe",
    "start_protected_game.exe",
    "gameoverlayui.exe",
    "epicgameslauncher.exe",
    "epicwebhelper.exe",
    "galaxyclient.exe",
    "galaxyclientservice.exe",
    "battle.net.exe",
    "agent.exe",  # Battle.net agent (often named Agent.exe under Battle.net)
    "riotclientservices.exe",
    "riotclientux.exe",
    "leagueclient.exe",
    "leagueclientux.exe",
    "valorant.exe",
    "fortniteclient-win64-shipping.exe",
    "minecraft.exe",
    "minecraftlauncher.exe",
    "robloxplayerbeta.exe",
    "robloxplayerlauncher.exe",
    # EA / Ubisoft / Rockstar / Xbox / itch
    "eadesktop.exe",
    "ealauncher.exe",
    "origin.exe",
    "upc.exe",
    "ubisoftconnect.exe",
    "ubisoftgamelauncher.exe",
    "rockstarservice.exe",
    "launcherpatcher.exe",
    "socialclub.exe",
    "gamingservices.exe",
    "gamingservicesnet.exe",
    "xboxapp.exe",
    "xboxpcapp.exe",
    "gamebar.exe",
    "itch.exe",
    # Desktop distraction clients (not browsers)
    "discord.exe",
    "discordptb.exe",
    "discordcanary.exe",
    "spotify.exe",
    "netflix.exe",
    "primevideo.exe",
    "disneyplus.exe",
    "hulu.exe",
    "twitch.exe",
]

# Categories that hard-kill when Armed (desktop apps only — never browsers).
HARD_BLOCK_DISTRACTION_CATEGORIES: frozenset[str] = frozenset(
    {
        "gaming",
        "video streaming",
        "music / media",
        "social media",
        "entertainment",
        "live streaming",
    }
)

# Path fragments that mean "this process is a game install / launcher tree"
_GAME_PATH_MARKERS: tuple[str, ...] = (
    "\\steam\\steamapps\\common\\",
    "\\steamapps\\common\\",
    "\\steam\\steamapps\\workshop\\",
    "\\epic games\\",
    "\\epicgames\\",
    "\\riot games\\",
    "\\xboxgames\\",
    "\\xbox games\\",
    "\\ea games\\",
    "\\electronic arts\\",
    "\\origin games\\",
    "\\ubisoft\\ubisoft game launcher\\",
    "\\ubisoft game launcher\\",
    "\\rockstar games\\",
    "\\gog galaxy\\games\\",
    "\\gog games\\",
    "\\itch\\apps\\",
    "\\battlenet\\",
    "\\battle.net\\",
)

_STEAM_NAME_PREFIXES: tuple[str, ...] = (
    "steam",
    "gameoverlay",
    "start_protected_game",
)

_LAUNCHER_NAME_MARKERS: tuple[str, ...] = (
    "epicgames",
    "epicgameslauncher",
    "galaxyclient",
    "battlenet",
    "riotclient",
    "leagueclient",
    "eadesktop",
    "ealauncher",
    "ubisoftconnect",
    "ubisoftgamelauncher",
    "rockstarservice",
    "gamingservices",
    "xboxapp",
    "xboxpcapp",
    "gamebar",
)

# Exact stems only (too short for prefix match)
_LAUNCHER_NAME_EXACT: frozenset[str] = frozenset(
    {
        "origin",
        "upc",
        "itch",
        "battle.net",
    }
)

# Never kill these even if listed (safety). Editors / shells stay usable while games die.
PROTECTED_EXES: frozenset[str] = frozenset(
    {
        "explorer.exe",
        "dwm.exe",
        "winlogon.exe",
        "csrss.exe",
        "services.exe",
        "lsass.exe",
        "svchost.exe",
        "system",
        "system idle process",
        "python.exe",
        "pythonw.exe",
        # IDE / editors — never hard-block (tracking still allowed)
        "cursor.exe",
        "cursor",
        "code.exe",
        "code - insiders.exe",
        "devenv.exe",
        "idea64.exe",
        "pycharm64.exe",
        "windsurf.exe",
        "powershell.exe",
        "pwsh.exe",
        "cmd.exe",
        "windows terminal.exe",
        "windowsterminal.exe",
        "conhost.exe",
        "searchhost.exe",
        "shellexperiencehost.exe",
        "applicationframehost.exe",
        "textinputhost.exe",
        "runtimebroker.exe",
        "sihost.exe",
        "fontdrvhost.exe",
    }
)

# Re-export Edge-only browser catalog (single source of truth).
from backend.behavior.browser_catalog import (  # noqa: E402
    ALLOWED_BROWSER_EXES,
    KNOWN_BROWSER_EXES,
    is_allowed_browser,
    is_browser_installer,
    is_known_browser,
    is_unauthorized_browser,
    normalize_exe as _catalog_normalize_exe,
    protected_browser_exes,
    unauthorized_kind,
)

PROTECTED_EXES = frozenset(PROTECTED_EXES | protected_browser_exes())


def normalize_exe(exe: str | None) -> str:
    return _catalog_normalize_exe(exe)


# While hard-block is armed + gate locked, close these so the tracker is harder to kill.
COMMITMENT_ESCAPE_EXES: frozenset[str] = frozenset(
    {
        "taskmgr.exe",
        "procexp.exe",
        "procexp64.exe",
        "perfmon.exe",
        "resmon.exe",
        "processhacker.exe",
    }
)


def hard_block_exe_set(policy: dict[str, Any]) -> set[str]:
    """Effective block list: user exes ∪ seed defaults (minus protected).

    Seed defaults always apply when ``hard_block_gaming`` is on so emptying the
    custom list cannot silently disable Steam/Epic launchers.
    """
    out: set[str] = set()
    for item in policy.get("hard_block_exes") or []:
        n = normalize_exe(str(item))
        if n and n not in PROTECTED_EXES:
            out.add(n)
    if policy.get("hard_block_gaming", True):
        for item in DEFAULT_HARD_BLOCK_EXES:
            n = normalize_exe(item)
            if n and n not in PROTECTED_EXES:
                out.add(n)
    return out


def is_protected_exe(exe: str | None) -> bool:
    from backend.behavior.browser_catalog import is_music_player_exe

    if normalize_exe(exe) in PROTECTED_EXES:
        return True
    # Pear / YouTube Music may report without .exe
    return is_music_player_exe(exe)


def is_commitment_escape_exe(exe: str | None) -> bool:
    return normalize_exe(exe) in COMMITMENT_ESCAPE_EXES


def process_exe_path(pid: int) -> str:
    if pid <= 0:
        return ""
    try:
        import psutil

        return (psutil.Process(pid).exe() or "").lower()
    except Exception:  # noqa: BLE001
        return ""


def looks_like_game_process(exe: str | None, pid: int = 0) -> bool:
    """True for Steam/Epic/Riot/EA/… launchers and games under known install folders."""
    name = normalize_exe(exe)
    if not name or name in PROTECTED_EXES:
        return False
    if name.endswith(".exe"):
        stem = name[:-4]
    else:
        stem = name
    for prefix in _STEAM_NAME_PREFIXES:
        if stem == prefix or stem.startswith(prefix):
            return True
    compact = stem.replace(" ", "").replace("-", "").replace("_", "")
    for marker in _LAUNCHER_NAME_MARKERS:
        if compact == marker or compact.startswith(marker):
            return True
    if stem in _LAUNCHER_NAME_EXACT or compact in _LAUNCHER_NAME_EXACT:
        return True
    # Common shipping exe suffixes from Unreal/Unity/store builds
    if stem.endswith("-win64-shipping") or stem.endswith("-win64-shipping.exe"):
        return True
    if "win64-shipping" in stem or "win32-shipping" in stem:
        return True
    path = process_exe_path(pid) if pid else ""
    if path:
        for marker in _GAME_PATH_MARKERS:
            if marker in path:
                return True
        # Steam client folder itself (not Common Files noise)
        if "\\steam\\" in path and "steamapps" not in path:
            if name.startswith("steam") or name in {
                "start_protected_game.exe",
                "gameoverlayui.exe",
            }:
                return True
        # Generic ...\Games\<title>\... when not a protected system path
        if "\\games\\" in path and "\\windows\\" not in path:
            return True
    return False


def _category_is_hard_block_distraction(category: str | None) -> bool:
    cat = (category or "").strip().lower()
    if not cat:
        return False
    if cat in HARD_BLOCK_DISTRACTION_CATEGORIES:
        return True
    # Gaming already listed; accept loose "Gaming (...)" labels if any
    return cat.startswith("gaming")


def is_game_bank_drain_target(
    exe: str | None,
    category: str | None,
    policy: dict[str, Any],
    *,
    pid: int = 0,
) -> bool:
    """True only for real games — never Task Manager / Discord / Spotify (those must not eat bank)."""
    if not policy.get("hard_block_enabled"):
        return False
    name = normalize_exe(exe)
    if not name or name in PROTECTED_EXES or name in COMMITMENT_ESCAPE_EXES:
        return False
    if is_known_browser(name) or is_allowed_browser(name):
        return False
    cat = (category or "").strip().lower()
    if cat == "gaming" or cat.startswith("gaming"):
        return True
    if policy.get("hard_block_gaming", True) and looks_like_game_process(exe, pid):
        return True
    # Seed list includes Discord/Spotify — those hard-block but do not drain game bank.
    return False


def should_hard_block(
    exe: str | None,
    category: str | None,
    policy: dict[str, Any],
    *,
    pid: int = 0,
) -> bool:
    """True if this foreground app should be killed while the gate is locked."""
    if not policy.get("hard_block_enabled"):
        return False
    name = normalize_exe(exe)
    if not name or name in PROTECTED_EXES:
        return False
    # Never hard-kill browsers — site blocking is extension/gate territory.
    if is_known_browser(name) or is_allowed_browser(name):
        return False
    # Close Task Manager / process tools so killing the tracker is harder (only while locked).
    if name in COMMITMENT_ESCAPE_EXES:
        return True
    if name in hard_block_exe_set(policy):
        return True
    if policy.get("hard_block_gaming", True):
        if _category_is_hard_block_distraction(category):
            return True
        # Steam launches real games as start_protected_game.exe / GameName.exe
        # under steamapps — those often classify as Other, not Gaming.
        if looks_like_game_process(exe, pid):
            return True
    return False


def list_blockable_pids(policy: dict[str, Any]) -> list[tuple[int, str]]:
    """Scan running processes for hard-block targets (not only foreground)."""
    if not policy.get("hard_block_enabled"):
        return []
    out: list[tuple[int, str]] = []
    seen: set[int] = set()
    try:
        import psutil
    except ImportError:
        return out
    for proc in psutil.process_iter(["pid", "name"]):
        try:
            pid = int(proc.info.get("pid") or 0)
            name = str(proc.info.get("name") or "")
        except (TypeError, ValueError):
            continue
        if pid <= 0 or pid in seen or is_protected_exe(name) or pid == os.getpid():
            continue
        if should_hard_block(name, None, policy, pid=pid):
            seen.add(pid)
            out.append((pid, name))
    return out


def terminate_blocked_process(pid: int, *, exe: str = "") -> bool:
    """Best-effort terminate. Returns True if a kill was attempted successfully.

    Never kills Microsoft Edge, catalog browsers, or Pear/YouTube Music — Edge is
    the allowed study shell; music players are not games. Soft-lock never calls
    this for browsers.
    """
    from backend.behavior.browser_catalog import is_music_player_exe

    if pid <= 0:
        return False
    if pid == os.getpid():
        return False
    if is_protected_exe(exe):
        log.info("Skip kill protected exe=%s pid=%s", exe, pid)
        return False
    if is_music_player_exe(exe):
        log.info("Skip kill music player exe=%s pid=%s", exe, pid)
        return False
    # Explicit Edge bail (defense in depth — even if catalog drifts).
    if is_allowed_browser(exe) or normalize_exe(exe) in {
        "msedge.exe",
        "msedgewebview2.exe",
        "msedge_proxy.exe",
    }:
        log.info("Skip kill allowed browser exe=%s pid=%s", exe, pid)
        return False
    try:
        import psutil

        proc = psutil.Process(pid)
        try:
            pname = proc.name()
        except (psutil.Error, OSError):
            pname = exe
        if is_protected_exe(pname):
            return False
        if is_music_player_exe(pname):
            log.info("Skip kill music player pname=%s pid=%s", pname, pid)
            return False
        if is_allowed_browser(pname) or normalize_exe(pname) in {
            "msedge.exe",
            "msedgewebview2.exe",
            "msedge_proxy.exe",
        }:
            log.info("Skip kill allowed browser pname=%s pid=%s", pname, pid)
            return False
        if normalize_exe(pname) in {"python.exe", "pythonw.exe"}:
            return False
        # Children first (Steam often leaves game child running)
        try:
            kids = proc.children(recursive=True)
        except (psutil.Error, OSError):
            kids = []
        for child in kids:
            try:
                cname = child.name()
                if is_protected_exe(cname) or is_allowed_browser(cname):
                    continue
                if is_music_player_exe(cname):
                    continue
                if normalize_exe(cname) in {
                    "msedge.exe",
                    "msedgewebview2.exe",
                    "msedge_proxy.exe",
                }:
                    continue
                child.terminate()
            except (psutil.Error, OSError):
                pass
        proc.terminate()
        try:
            proc.wait(timeout=2)
        except (psutil.TimeoutExpired, psutil.Error):
            try:
                proc.kill()
            except (psutil.Error, OSError) as exc:
                log.warning("kill failed pid=%s: %s — trying taskkill", pid, exc)
                try:
                    import subprocess

                    subprocess.run(
                        ["taskkill", "/F", "/T", "/PID", str(pid)],
                        capture_output=True,
                        timeout=5,
                        check=False,
                        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                    )
                except Exception as exc2:  # noqa: BLE001
                    log.warning("taskkill failed pid=%s: %s", pid, exc2)
                    return False
        log.info("Hard-blocked pid=%s exe=%s", pid, pname or exe)
        return True
    except Exception as exc:  # noqa: BLE001
        log.warning("terminate_blocked_process failed pid=%s: %s", pid, exc)
        return False


def _suggested_wake_note(
    db: Session,
    user_id: int,
    day_date,
    next_step: str,
) -> dict[str, Any] | None:
    """Soft wake hint from last sleep end + morning bible gate — not a device alarm."""
    try:
        from backend.models.wearable_daily import WearableDaily
        from backend.wearables.sleep_window import parse_sleep_dict, sleep_datetimes
        from backend.planner.service import local_tz

        row = (
            db.query(WearableDaily)
            .filter(
                WearableDaily.user_id == user_id,
                WearableDaily.local_date <= day_date,
                WearableDaily.sleep_hours.isnot(None),
                WearableDaily.sleep_hours > 0,
            )
            .order_by(WearableDaily.local_date.desc())
            .first()
        )
        if not row:
            return None
        sleep = parse_sleep_dict(row.payload_json)
        window = sleep_datetimes(local_date=row.local_date, sleep=sleep, tz=local_tz())
        if not window:
            return {
                "sleep_hours": float(row.sleep_hours) if row.sleep_hours is not None else None,
                "wake_local": None,
                "note": (
                    "Sleep hours on file, but no start/end for a wake time. "
                    "Device smart alarm stays on the watch — CALT cannot write it."
                ),
                "bible_pending": next_step == "bible",
                "writable_alarm": False,
            }
        _start, end_dt = window
        wake_txt = end_dt.strftime("%H:%M")
        note = f"Last sleep ended ~{wake_txt} local."
        if next_step == "bible":
            note += " Morning gate: Bible first, then plan — soft ritual, not a hardware alarm."
        else:
            note += " Soft suggestion only — Zepp/T-Rex smart alarm write is deferred."
        return {
            "sleep_hours": float(row.sleep_hours) if row.sleep_hours is not None else None,
            "wake_local": end_dt.isoformat(),
            "wake_clock": wake_txt,
            "sleep_date": row.local_date.isoformat(),
            "note": note,
            "bible_pending": next_step == "bible",
            "writable_alarm": False,
        }
    except Exception as exc:  # noqa: BLE001
        log.debug("suggested_wake skipped: %s", exc)
        return None


def compute_distraction_gate(db: Session, user_id: int) -> dict[str, Any]:
    """Games locked unless: day unlimited (study goal + 1 chapter) or day pass."""
    from backend.behavior.category_scores import load_score_map
    from backend.behavior.demo_clock import is_demo, now_local, status as demo_status
    from backend.behavior.productivity_policy import load_policy_dict, resolve_session_score
    from backend.bible import store as bible_store
    from backend.models.timetable import TrackedSession
    from backend.planner.service import local_day_bounds_utc, local_tz

    policy = load_policy_dict(db, user_id)
    enabled = bool(policy.get("hard_block_enabled"))
    goal = max(1, int(policy.get("daily_goal_minutes") or 240))
    threshold = int(policy.get("threshold") or 60)

    demo_on = is_demo()
    gate_now = now_local()
    day_date = gate_now.date()
    start, end = local_day_bounds_utc(day_date)
    # Same scope as stats APIs: admin tracker rows + legacy demo mis-attributions.
    from backend.models import User
    from backend.timetable.tracker_query import tracker_user_ids

    get_row = getattr(db, "get", None)
    gate_user = get_row(User, user_id) if callable(get_row) else None
    uid_scope = tracker_user_ids(db, gate_user) if gate_user is not None else [user_id]
    sessions = (
        db.query(TrackedSession)
        .filter(
            TrackedSession.user_id.in_(uid_scope),
            TrackedSession.start_time < end,
            TrackedSession.end_time > start,
        )
        .all()
    )
    scores = load_score_map(db)

    def score_fn(sess):
        return resolve_session_score(sess, scores, policy)

    productive = 0
    # Wall-clock union of productive intervals (avoids double-count Edge desktop + extension).
    intervals: list[tuple[datetime, datetime]] = []
    for s in sessions:
        if not s.start_time or not s.end_time:
            continue
        if score_fn(s) < threshold:
            continue
        a = s.start_time
        b = s.end_time
        if a.tzinfo is None:
            a = a.replace(tzinfo=UTC)
        if b.tzinfo is None:
            b = b.replace(tzinfo=UTC)
        a = max(a, start)
        b = min(b, end)
        if b > a:
            intervals.append((a, b))
    intervals.sort(key=lambda t: t[0])
    merged: list[tuple[datetime, datetime]] = []
    for a, b in intervals:
        if not merged or a > merged[-1][1]:
            merged.append((a, b))
        else:
            merged[-1] = (merged[-1][0], max(merged[-1][1], b))

    # PC left on while sleeping must not count toward the study goal.
    from backend.wearables.sleep_window import sleep_bouts_for_user_day, subtract_intervals

    sleep_windows = sleep_bouts_for_user_day(db, user_id, day_date, pad_days=1)
    sleep_cut: list[tuple[datetime, datetime]] = []
    for ss, se in sleep_windows:
        if ss.tzinfo is None:
            ss = ss.replace(tzinfo=UTC)
        else:
            ss = ss.astimezone(UTC)
        if se.tzinfo is None:
            se = se.replace(tzinfo=UTC)
        else:
            se = se.astimezone(UTC)
        a = max(ss, start)
        b = min(se, end)
        if b > a:
            sleep_cut.append((a, b))
    if sleep_cut:
        merged = subtract_intervals(merged, sleep_cut)

    for a, b in merged:
        productive += int((b - a).total_seconds() // 60)

    bible = bible_store.summary(user_id)
    bible_minutes = float(bible.get("bible_minutes") or 0)
    bank_remaining_s = int(bible.get("game_bank_remaining_seconds") or 0)
    bank_remaining_m = float(bible.get("game_bank_remaining_minutes") or 0)
    day_pass = bool(bible.get("day_pass"))
    reward_day = bool(bible.get("reward_day"))
    chapter_goal = bible.get("chapter_goal") or {}
    chapters_today = list(bible.get("chapters_completed_today") or [])
    chapter_met = bool(chapter_goal.get("met")) or len(chapters_today) >= 1
    from backend.behavior import reward_days

    reward_status = reward_days.record_qualifying_day(
        user_id,
        qualified=productive >= goal and chapter_met,
    )
    # Study goal + ≥1 chapter, a controlled day pass, or an earned reward day
    # unlocks games and normal browsing until midnight.
    day_unlimited = bool(reward_day or day_pass or (productive >= goal and chapter_met))
    # Legacy bank no longer unlocks midday (chapter+study is the primary path)
    has_bank = False
    unlocked = (not enabled) or day_unlimited
    remaining = max(0, goal - productive) if enabled and not day_unlimited else 0

    # Morning web gate (SPA) — separate from desktop game unlock.
    # Bible first (day-pass does NOT skip morning Bible), then confirm today's plan
    # inside the plan window (MORNING_PLAN_START → MORNING_PLAN_EOD).
    import os

    from backend.planner import morning_plan as morning_store

    morning_on = os.environ.get("MORNING_GATE", "1").strip().lower() not in (
        "0",
        "false",
        "no",
        "off",
    )
    bible_done = bool(chapter_met)  # intentional: day_pass does not skip morning Bible
    blocks_today = morning_store.count_blocks_today(db, user_id, day_date)
    plan_confirmed = morning_store.is_plan_confirmed(user_id, day_date)
    # Confirmation is explicit only (Productivity Confirm / morning-plan API).
    # Having calendar blocks does NOT auto-satisfy the morning plan gate.
    plan_done = bool(plan_confirmed)

    from backend.planner import morning_rewards as morning_rewards_store

    # Lazy catch-up: Bible done elsewhere (tracker) → grant + expose rewards
    if bible_done and not demo_on:
        try:
            morning_rewards_store.maybe_grant_bible(user_id)
        except Exception:
            pass
    rewards = morning_rewards_store.summary(user_id, day_date)
    bible_award = (rewards.get("awards") or {}).get("bible") or {}
    bible_completed_at = bible_award.get("granted_at") if bible_award.get("granted") else None

    plan_window = morning_store.evaluate_plan_window(
        bible_done=bible_done,
        bible_completed_at=bible_completed_at,
        now=gate_now,
    )

    if not morning_on:
        next_step = "open"
    elif not bible_done:
        next_step = "bible"
    elif plan_done:
        next_step = "open"
    elif plan_window.get("phase") == "after_eod":
        # Past EOD without confirm — don't force plan for today; resets next calendar day
        next_step = "open"
    else:
        # Before window or during window: stay on plan (confirm may be disabled)
        next_step = "plan"

    # An earned reward day is the explicit all-day browser/game reward. Unlike
    # a weekly day-pass, it also bypasses the morning browser redirect.
    if reward_day:
        next_step = "open"

    # Website stays navigable during demos; SelfTracker still uses browser.mode.
    if demo_on:
        allow_paths = ["*"]
    elif next_step == "bible":
        allow_paths = ["/bible", "/login"]
    elif next_step == "plan":
        allow_paths = ["/bible", "/productivity", "/login"]
    else:
        allow_paths = ["*"]

    # Read-only auto-plan status for UI / Jarvis — never draft or confirm here.
    # Drafting belongs to explicit POST /morning-plan/auto-draft (or Bible UI action).
    auto_plan_payload: dict | None = None
    try:
        from backend.planner import auto_plan as auto_plan_mod

        auto_plan_payload = auto_plan_mod.auto_plan_summary(user_id, day_date)
    except Exception:
        auto_plan_payload = None

    from backend.behavior.browser_gate_policy import (
        DEFAULT_BIBLE_URL,
        DEFAULT_PLAN_URL,
        build_browser_gate_section,
    )
    from backend.behavior.tracker_plan import fetch_plan_context

    bible_url = DEFAULT_BIBLE_URL
    plan_url = DEFAULT_PLAN_URL
    locked_flag = bool(enabled and not unlocked)

    planner_category: str | None = None
    planner_title: str | None = None
    planner_minutes_left: int | None = None
    try:
        plan_ctx = fetch_plan_context(user_id, now=gate_now, db=db)
        if plan_ctx.current is not None:
            planner_category = plan_ctx.current.category
            planner_title = plan_ctx.current.title
            planner_minutes_left = int(plan_ctx.current.minutes_left)
    except Exception as exc:  # noqa: BLE001
        log.debug("plan context for browser mode skipped: %s", exc)

    hint = morning_store.morning_hint_for(
        next_step,
        plan_window=plan_window,
        rewards_total=int(rewards.get("total_points") or 0),
        morning_on=morning_on,
    )

    daily_practice: dict[str, Any] | None = None
    if plan_done or next_step == "open":
        try:
            from backend.quiz.daily_practice import build_daily_practice_nudge

            daily_practice = build_daily_practice_nudge(db, user_id=user_id)
        except Exception as exc:  # noqa: BLE001
            log.debug("daily_practice nudge skipped: %s", exc)

    auto_plan_cfg_on = True
    auto_plan_confirm_on = False
    try:
        from backend.planner import auto_plan as auto_plan_mod

        auto_plan_cfg_on = bool(auto_plan_mod.morning_auto_plan_enabled())
        auto_plan_confirm_on = bool(auto_plan_mod.morning_auto_plan_confirm())
    except Exception:
        pass

    morning = {
        "enabled": morning_on,
        "day": day_date.isoformat(),
        "bible_done": bible_done,
        "plan_done": plan_done,
        "plan_confirmed": plan_confirmed,
        "blocks_today": int(blocks_today),
        "next": next_step,
        "allow_paths": allow_paths,
        "bible_url": bible_url,
        "plan_url": plan_url,
        "redirect_url": (
            bible_url if next_step == "bible" else plan_url if next_step == "plan" else None
        ),
        "rewards": rewards,
        "plan_window": plan_window,
        "hint": hint,
        "auto_plan": auto_plan_payload,
        "daily_practice": daily_practice,
        # Soft only — CALT cannot write Zepp/T-Rex hardware smart alarms
        "suggested_wake": _suggested_wake_note(db, user_id, day_date, next_step),
        # Read-only env knobs for Productivity Settings (not writable via API)
        "config": {
            "gate": morning_on,
            "plan_start": morning_store.plan_start_hhmm(),
            "plan_eod": morning_store.plan_eod_hhmm(),
            "auto_plan": auto_plan_cfg_on,
            "auto_plan_confirm": auto_plan_confirm_on,
        },
    }

    browser = build_browser_gate_section(
        enabled=enabled,
        locked=locked_flag,
        morning_next=next_step,
        planner_category=planner_category,
        planner_title=planner_title,
        bible_url=bible_url,
        plan_url=plan_url,
        day_unlimited=day_unlimited,
        now=gate_now,
    )
    day_mode = str(browser.get("mode") or "study")

    locked_extras: dict[str, Any] = {"suggested_links": [], "current_block": None}
    try:
        from backend.behavior.locked_screen import build_locked_screen_extras

        locked_extras = build_locked_screen_extras(
            db,
            user_id,
            bible_url=bible_url,
            plan_url=plan_url,
            allow_domains=list(browser.get("allow_domains") or []),
            planner_title=planner_title,
            planner_category=planner_category,
            planner_minutes_left=planner_minutes_left,
            morning_next=next_step,
        )
    except Exception as exc:  # noqa: BLE001
        log.debug("locked screen extras skipped: %s", exc)

    return {
        "enabled": enabled,
        "locked": locked_flag,
        "unlocked": unlocked,
        "productive_minutes": productive,
        "daily_goal_minutes": goal,
        "remaining_minutes": remaining,
        "hard_block_gaming": bool(policy.get("hard_block_gaming", True)),
        "hard_block_exes": list(policy.get("hard_block_exes") or []),
        "day": day_date.isoformat(),
        "bible_minutes": bible_minutes,
        "chapters_completed_today": chapters_today,
        "chapter_goal": chapter_goal,
        "chapter_goal_met": chapter_met,
        "game_bank_remaining_minutes": bank_remaining_m,
        "game_bank_remaining_seconds": bank_remaining_s,
        "game_bank_earned_minutes": float(bible.get("game_bank_earned_minutes") or 0),
        "game_bank_consumed_minutes": float(bible.get("game_bank_consumed_minutes") or 0),
        "day_unlimited": day_unlimited,
        "day_pass": day_pass,
        "day_pass_status": bible.get("day_pass_status"),
        "reward_day": reward_day,
        "reward_day_status": reward_status,
        "unlock_mode": (
            "off"
            if not enabled
            else "unlimited"
            if day_unlimited
            else "bank"
            if has_bank
            else "locked"
        ),
        "morning": morning,
        "browser": browser,
        "browser_mode": day_mode,
        "demo": demo_status(),
        "suggested_links": list(locked_extras.get("suggested_links") or []),
        "current_block": locked_extras.get("current_block"),
    }
