"""Poll loop, session lifecycle, idle/sleep handling."""

from __future__ import annotations

import atexit
import contextlib
import json
import logging
import queue
import threading
import time
from dataclasses import dataclass, field
from typing import Callable, Optional

from backend.behavior.session_key import is_browser_exe, session_identity
from backend.behavior.tracker_classify import classify_app
from backend.behavior.tracker_ignore import is_ignored_app
from backend.behavior.tracker_idle import get_idle_seconds
from backend.behavior.tracker_storage import (
    CONFIG_PATH,
    SessionCheckpoint,
    TrackerConfig,
    consume_flush_request,
    enable_sqlite_wal,
    enqueue_event,
    flush_pending_events,
    persist_event,
    resolve_user_id,
    resolve_username,
    today_total_seconds,
    tracker_log_path,
    write_flush_ack,
)
from backend.behavior.tracker_plan import PlanContext, fetch_plan_context
from backend.behavior.tracker_win32 import get_foreground_info

log = logging.getLogger("desktop_tracker")

PLAN_REFRESH_S = 60.0
GATE_REFRESH_S = 30.0

ForegroundFn = Callable[[], tuple[str, str, int]]


@dataclass
class ActiveSession:
    exe: str
    title: str
    pid: int
    group_key: str
    site: str
    latest_title: str
    category: str
    score: int
    started_at: float = field(default_factory=time.time)

    def age(self) -> float:
        return time.time() - self.started_at

    def to_dict(self) -> dict:
        return {
            "exe": self.exe,
            "title": self.latest_title,
            "pid": self.pid,
            "group_key": self.group_key,
            "site": self.site,
            "latest_title": self.latest_title,
            "category": self.category,
            "score": self.score,
            "started_at": self.started_at,
        }

    @classmethod
    def from_dict(cls, data: dict) -> ActiveSession:
        exe = str(data.get("exe", ""))
        title = str(data.get("title", "") or data.get("latest_title", ""))
        group_key, site = session_identity(exe, title)
        if data.get("group_key"):
            group_key = str(data["group_key"])
        if data.get("site"):
            site = str(data["site"])
        cat, score = classify_app(exe, title)
        return cls(
            exe=exe,
            title=title,
            pid=int(data.get("pid") or 0),
            group_key=group_key,
            site=site,
            latest_title=str(data.get("latest_title") or title),
            category=str(data.get("category") or cat),
            score=int(data.get("score") or score),
            started_at=float(data.get("started_at") or time.time()),
        )

    @classmethod
    def start(cls, exe: str, title: str, pid: int) -> ActiveSession:
        group_key, site = session_identity(exe, title)
        category, score = classify_app(exe, title)
        return cls(
            exe=exe,
            title=title,
            pid=pid,
            group_key=group_key,
            site=site,
            latest_title=title,
            category=category,
            score=score,
        )

    def to_event(self, reason: str, *, end_at: float | None = None) -> dict:
        _, site = session_identity(self.exe, self.latest_title)
        category, score = classify_app(self.exe, self.latest_title)
        domain = site if is_browser_exe(self.exe) else self.exe
        end = end_at if end_at is not None else time.time()
        duration = max(0, round(end - self.started_at))
        ev = {
            "type": "SESSION_END",
            "source": "desktop_tracker",
            "exe": self.exe,
            "title": self.latest_title[:200],
            "domain": domain,
            "category": category,
            "productivity_score": score,
            "duration_seconds": duration,
            "timestamp": int(self.started_at * 1000),
            "end_timestamp": int(end * 1000),
            "reason": reason,
            "pid": self.pid,
            "group_key": self.group_key,
        }
        return ev


class TrackerService:
    def __init__(
        self,
        config: TrackerConfig | None = None,
        foreground_fn: ForegroundFn | None = None,
    ) -> None:
        self.config = config or TrackerConfig.load()
        self._foreground = foreground_fn or get_foreground_info
        self._current: Optional[ActiveSession] = None
        self._last_poll_at: float = time.time()
        self._paused = threading.Event()
        self._stop = threading.Event()
        self._shutdown_done = False
        self._thread: threading.Thread | None = None
        self._ws_queue: queue.Queue[dict] = queue.Queue(maxsize=300)
        self._user_id: int = 0
        self._username: str = ""
        self._lock = threading.RLock()
        self._plan_context: PlanContext | None = None
        self._plan_updated_at: float = 0.0
        self._gate: dict | None = None
        self._gate_policy: dict | None = None
        self._gate_updated_at: float = 0.0
        self._last_browser_mode: str | None = None
        self._last_checkpoint_at: float = 0.0
        self._last_bulk_tick_at: float = time.time()
        self._last_goals_check_at: float = 0.0
        self._was_idle: bool = False
        self._idle_since_at: float | None = None
        self._last_block_kill_at: float = 0.0
        self._last_soft_lock_at: float = 0.0
        self._last_keyword_hit: str = ""
        self._last_keyword_hit_at: float = 0.0
        self._last_watch_leak_at: float = 0.0
        self._nsfw_inactive_spoken: bool = False
        self._nsfw_status_line: str | None = None

    @property
    def paused(self) -> bool:
        return self._paused.is_set()

    def set_paused(self, value: bool) -> None:
        if value and (self._gate_policy or {}).get("hard_block_enabled"):
            log.info("[hard_block] pause ignored — hard-block is armed")
            self._paused.clear()
            return
        if value:
            self._paused.set()
            self.flush_current("pause")
            flush_pending_events()
        else:
            self._paused.clear()

    def today_seconds(self) -> int:
        if not self._user_id:
            return 0
        flush_pending_events()
        return today_total_seconds(self._user_id)

    def plan_context(self) -> PlanContext | None:
        return self._plan_context

    @property
    def user_id(self) -> int:
        return self._user_id

    @property
    def username(self) -> str:
        return self._username or (f"user#{self._user_id}" if self._user_id else "—")

    def latest_gate(self, *, force: bool = False) -> dict:
        """Return cached distraction-gate payload (refresh if due or force)."""
        if force:
            self._gate_updated_at = 0.0
        self._refresh_gate_if_due()
        return dict(self._gate or {})

    def hard_block_armed(self) -> bool:
        """True when hard-block / distraction gate is Armed (enabled)."""
        policy = self._gate_policy or {}
        if "hard_block_enabled" in policy:
            return bool(policy.get("hard_block_enabled"))
        return bool((self._gate or {}).get("enabled"))

    def _refresh_plan_if_due(self) -> None:
        if not self._user_id:
            return
        now = time.time()
        if now - self._plan_updated_at < PLAN_REFRESH_S:
            return
        try:
            self._plan_context = fetch_plan_context(self._user_id)
            self._plan_updated_at = now
        except Exception as exc:  # noqa: BLE001
            log.debug("Plan context refresh failed: %s", exc)

    def _refresh_stack_health_if_due(self) -> None:
        """Probe API/Vite (cached ~20s). Jarvis one-liner on down transition."""
        try:
            from backend.behavior.stack_health import (
                get_stack_health,
                maybe_jarvis_stack_down_line,
            )

            health = get_stack_health()
            line = maybe_jarvis_stack_down_line()
            if line:
                log.info("[stack_health] %s", health.status_line())
                try:
                    from backend.behavior.stack_health import (
                        jarvis_category_for_down,
                        local_jarvis_speak,
                    )

                    kind = "both"
                    if "API and Web" in line:
                        kind = "both"
                    elif "API is down" in line:
                        kind = "api"
                    else:
                        kind = "web"
                    local_jarvis_speak(jarvis_category_for_down(kind), force=False)
                except Exception:  # noqa: BLE001
                    try:
                        from backend.behavior.voice_agent.announce import surface_dialogue
                        from backend.behavior.gate_alerts import speak_alert

                        surface_dialogue(line, source="stack_health")
                        speak_alert(line, force=False)
                    except Exception:  # noqa: BLE001
                        pass
        except Exception as exc:  # noqa: BLE001
            log.debug("stack health refresh skipped: %s", exc)

    def _refresh_gate_if_due(self) -> None:
        if not self._user_id:
            return
        now = time.time()
        if now - self._gate_updated_at < GATE_REFRESH_S:
            return
        try:
            from backend.behavior.distraction_gate import compute_distraction_gate
            from backend.behavior.productivity_policy import load_policy_dict
            from backend.db.base import SessionLocal

            db = SessionLocal()
            try:
                self._gate = compute_distraction_gate(db, self._user_id)
                self._gate_policy = load_policy_dict(db, self._user_id)
                self._gate_updated_at = now
            finally:
                db.close()
        except Exception as exc:  # noqa: BLE001
            log.debug("Distraction gate refresh failed: %s", exc)
        else:
            g = self._gate or {}
            # FREE / reward day: pause Jarvis so games get VRAM/CPU/GPU.
            try:
                from backend.behavior.voice_agent import sync_voice_with_browser_gate

                sync_voice_with_browser_gate(g, user_id=self._user_id)
            except Exception as exc:  # noqa: BLE001
                log.debug("voice free-mode sync skipped: %s", exc)
            if g.get("enabled"):
                log.info(
                    "[hard_block] gate locked=%s productive=%s/%s remaining=%s",
                    g.get("locked"),
                    g.get("productive_minutes"),
                    g.get("daily_goal_minutes"),
                    g.get("remaining_minutes"),
                )
            # Once-per-day canned morning brief (after 5am; bible/plan pending)
            try:
                from backend.behavior.voice_agent.morning_brief import (
                    maybe_speak_morning_brief,
                )

                maybe_speak_morning_brief(
                    self._user_id,
                    source="tracker_gate",
                    require_morning_gate=True,
                )
            except Exception as exc:  # noqa: BLE001
                log.debug("morning brief skipped: %s", exc)

            # Mode switch canned line (Jarvis)
            try:
                browser = (g.get("browser") or {}) if isinstance(g, dict) else {}
                mode = str(browser.get("mode") or g.get("browser_mode") or "").strip().lower()
                if mode and mode != self._last_browser_mode:
                    prev = self._last_browser_mode
                    self._last_browser_mode = mode
                    if prev is not None:
                        from backend.behavior.gate_alerts import speak_alert
                        from backend.behavior.voice_agent import dialogues as dlg

                        line = dlg.pick(f"mode_{mode}", mode="rotate")
                        if line:
                            speak_alert(line, force=False)
            except Exception as exc:  # noqa: BLE001
                log.debug("mode switch announce skipped: %s", exc)

            # Re-assert HKCU Run while Armed (discourage casual uninstall)
            try:
                from backend.behavior.tracker_persist import maybe_protect_startup

                maybe_protect_startup(armed=bool(g.get("enabled")))
            except Exception as exc:  # noqa: BLE001
                log.debug("persist protect skipped: %s", exc)

    def _maybe_hard_block(self, exe: str, title: str, pid: int) -> bool:
        """Kill blocked apps while gate is locked. Returns True if killed."""
        gate = self._gate or {}
        policy = self._gate_policy or {}
        if not policy.get("hard_block_enabled"):
            # Rate-limited breadcrumb so "games not blocked" is diagnosable from logs.
            now = time.time()
            if now - getattr(self, "_last_disarmed_hint_at", 0.0) >= 120.0:
                from backend.behavior.distraction_gate import looks_like_game_process

                if looks_like_game_process(exe, pid):
                    self._last_disarmed_hint_at = now
                    log.info(
                        "[hard_block] Disarmed — not killing %s (Arm in Productivity Policy)",
                        exe,
                    )
            return False

        from backend.behavior.distraction_gate import (
            is_game_bank_drain_target,
            list_blockable_pids,
            should_hard_block,
            terminate_blocked_process,
        )
        from backend.behavior.tracker_classify import classify_app
        from backend.bible import store as bible_store

        category, _score = classify_app(exe, title)
        # Bank drains only for real games — never Task Manager / process tools.
        drains_bank = is_game_bank_drain_target(exe, category, policy, pid=pid)

        # Drain game bank while a game is in the foreground (unless day unlimited)
        if (
            self._user_id
            and drains_bank
            and not gate.get("day_unlimited")
            and int(gate.get("game_bank_remaining_seconds") or 0) > 0
        ):
            left = bible_store.consume_game_seconds(self._user_id, max(0.5, self._poll_interval()))
            # Refresh gate soon after drain
            self._gate_updated_at = 0
            if left > 0:
                return False

        if not gate.get("locked"):
            # Recompute quickly if bank may have just hit zero
            if drains_bank and not gate.get("day_unlimited"):
                self._refresh_gate_if_due()
                gate = self._gate or {}
            if not gate.get("locked"):
                return False

        targets: list[tuple[int, str]] = []
        if should_hard_block(exe, category, policy, pid=pid):
            targets.append((pid, exe))
        # Also sweep Steam/game processes that are not foreground yet
        now = time.time()
        if now - self._last_block_kill_at >= 2.0:
            for spid, sname in list_blockable_pids(policy):
                if spid != pid:
                    targets.append((spid, sname))

        if not targets:
            return False

        killed_any = False
        if self._current and any(t[0] == self._current.pid for t in targets):
            self.flush_current("hard_block", end_at=now)

        for tpid, tname in targets:
            if terminate_blocked_process(tpid, exe=tname):
                killed_any = True
                log.info(
                    "[hard_block] killed %s (pid=%s) — mode=%s bank=%ss left",
                    tname,
                    tpid,
                    gate.get("unlock_mode"),
                    gate.get("game_bank_remaining_seconds"),
                )
        if killed_any:
            self._last_block_kill_at = now
            try:
                from backend.behavior.tracker_block_gui import show_hard_block_notice

                show_hard_block_notice(
                    blocked_app=targets[0][1] if targets else exe,
                    gate=gate,
                    user_id=self._user_id,
                )
            except Exception as exc:  # noqa: BLE001
                log.debug("hard-block notice: %s", exc)
        return killed_any

    def _gate_enforcing(self) -> bool:
        """Armed, morning bible/plan, or day-mode browser.enforce (study/free/…)."""
        gate = self._gate or {}
        policy = self._gate_policy or {}
        if policy.get("hard_block_enabled"):
            return True
        browser = gate.get("browser") or {}
        if browser.get("enforce"):
            return True
        morning = gate.get("morning") or {}
        next_step = str(morning.get("next") or "open").strip().lower()
        return next_step in ("bible", "plan")

    def _soft_lock_notice(self, label: str, *, kind: str) -> None:
        """Show lock card + rate-limited voice; never kills browsers/IDEs."""
        now = time.time()
        if now - self._last_soft_lock_at < 20.0:
            return
        self._last_soft_lock_at = now
        try:
            from backend.behavior.gate_alerts import line_for, speak_alert
            from backend.behavior.tracker_block_gui import show_nsfw_screen_notice

            speak_alert(line_for(kind))
            show_nsfw_screen_notice(
                detail=label,
                gate=self._gate,
                user_id=self._user_id,
            )
        except Exception as exc:  # noqa: BLE001
            log.debug("soft-lock notice: %s", exc)

    def _maybe_unauthorized_browser(self, exe: str) -> bool:
        """Soft-lock if Chrome/Brave/installer/etc while enforcing. Never process-kill."""
        if not self._gate_enforcing():
            return False
        from backend.behavior.browser_catalog import is_music_player_exe, unauthorized_kind

        if is_music_player_exe(exe):
            log.info(
                "[gate] soft-lock skip Edge/music — exe=%s is Pear/YouTube Music (not a browser)",
                exe,
            )
            return False
        kind = unauthorized_kind(exe)
        if not kind:
            return False
        log.info("[gate] %s foreground=%s (soft-lock overlay only; never kill Edge)", kind, exe)
        self._soft_lock_notice(exe, kind=kind)
        return True

    def _maybe_title_keyword_block(self, exe: str, title: str) -> bool:
        """Cheap window-title keyword check (no keylogging / no DOM)."""
        if not self._gate_enforcing() or not title:
            return False
        from backend.behavior.browser_catalog import is_music_player_exe

        # Pear / YouTube Music titles are song names — do not soft-lock Edge for them.
        if is_music_player_exe(exe):
            return False
        browser = (self._gate or {}).get("browser") or {}
        if browser and browser.get("block_keywords") is False:
            return False
        from backend.behavior.browser_gate_policy import url_or_title_hits_keywords

        hit = url_or_title_hits_keywords("", title)
        if not hit:
            return False
        if hit == self._last_keyword_hit and (time.time() - self._last_soft_lock_at) < 60:
            return True
        self._last_keyword_hit = hit
        log.info("[gate] keyword hit in title=%r matched=%s exe=%s", title[:80], hit, exe)
        self._soft_lock_notice(f"keyword:{hit}", kind="keyword")
        return True

    def _mode_blocks_watch(self) -> bool:
        g = self._gate or {}
        # Daily focus goal met → free browsing (adult filter still on elsewhere).
        if g.get("day_unlimited"):
            return False
        browser = g.get("browser") or {}
        mode = str(browser.get("mode") or "").strip().lower()
        if mode in ("bible", "planning", "study"):
            return True
        return bool(browser.get("block_watch_sites"))

    def _maybe_watch_title_leak(self, exe: str, title: str) -> bool:
        """If policy blocks watch but YouTube/Netflix is still foreground — soft-lock.

        Catches extension miss (not loaded / old / InPrivate) and unauthorized
        browsers (Chrome/Brave) where only the tracker can see the window title.

        Never fires for Pear Desktop / YouTube Music (Electron music players) —
        their titles contain "YouTube" but they are not browsers. Soft-lock must
        not auto-open Bible / storm Edge when music is the foreground offender.

        Never fires after ``day_unlimited`` (daily goal met → free mode).
        """
        if not self._mode_blocks_watch() or not title:
            return False
        from backend.behavior.browser_catalog import is_music_player_exe
        from backend.behavior.session_key import is_browser_exe

        if is_music_player_exe(exe):
            log.info(
                "[gate] soft-lock skip music player exe=%s title=%r (not a browser)",
                exe,
                (title or "")[:80],
            )
            return False
        # Watch-leak overlay is for real browsers only — never Electron shells.
        if not is_browser_exe(exe):
            from backend.behavior.browser_catalog import is_known_browser

            if not is_known_browser(exe):
                return False
        t = (title or "").lower()
        # Allowlisted study shells (Scaler / Colab / GitHub) — never treat as watch
        # leak even if a background tab title somehow bleeds into the window string.
        allow_title_markers = (
            "scaler",
            "colab",
            "github",
            "leetcode",
            "localhost",
            "5173",
            "cognitive-aware",
        )
        if any(m in t for m in allow_title_markers):
            return False
        # Music.youtube / "YouTube Music" in a browser tab is still watch content;
        # desktop music apps already returned above.
        markers = ("youtube", "youtu.be", "netflix", "twitch", "prime video", "disney+")
        if not any(m in t for m in markers):
            return False
        now = time.time()
        if now - self._last_watch_leak_at < 45.0:
            return True
        self._last_watch_leak_at = now
        mode = str(((self._gate or {}).get("browser") or {}).get("mode") or "study")
        log.warning(
            "[gate] watch leak foreground exe=%s title=%r mode=%s — extension may not be blocking",
            exe,
            title[:100],
            mode,
        )
        try:
            from backend.behavior.gate_alerts import speak_alert
            from backend.behavior.tracker_block_gui import show_hard_block_notice

            speak_alert(
                "Watch sites are blocked until your daily focus goal is met. "
                "Use Microsoft Edge with SelfTracker loaded.",
                force=False,
            )
            if now - self._last_soft_lock_at >= 20.0:
                self._last_soft_lock_at = now
                # Overlay only — never auto-open Bible (that launched Edge + FOCUS storms).
                show_hard_block_notice(
                    blocked_app="Watch blocked until daily goal — check Edge SelfTracker",
                    gate=self._gate,
                    user_id=self._user_id,
                    auto_open_bible=False,
                )
        except Exception as exc:  # noqa: BLE001
            log.debug("watch-leak notice: %s", exc)
        return True

    def _maybe_nsfw_screen_scan(self) -> None:
        """Occasional CPU NSFW screenshot when Armed or day enforce — never kills browsers."""
        armed = bool((self._gate_policy or {}).get("hard_block_enabled"))
        browser = (self._gate or {}).get("browser") or {}
        day_enforce = bool(browser.get("enforce"))
        try:
            from backend.behavior.nsfw_screen_scan import maybe_scan_screen, scan_status

            st = scan_status()
            self._nsfw_status_line = str(st.get("message") or "") or None
            if not st.get("active") and st.get("backend") == "none" and not self._nsfw_inactive_spoken:
                self._nsfw_inactive_spoken = True
                try:
                    from backend.behavior.gate_alerts import speak_alert

                    speak_alert(
                        "NSFW scan inactive: install nudenet or place an onnx model in data nsfw.",
                        force=False,
                    )
                except Exception as exc:  # noqa: BLE001
                    log.debug("nsfw inactive speak: %s", exc)

            result = maybe_scan_screen(
                hard_block_armed=armed,
                day_enforce=day_enforce,
            )
        except Exception as exc:  # noqa: BLE001
            log.debug("nsfw scan: %s", exc)
            return
        if result.positive:
            self._soft_lock_notice(
                f"score={result.score:.2f}/{result.backend}",
                kind="nsfw_screen",
            )

    def nsfw_status_line(self) -> str | None:
        """Latest NSFW scan status line for Today's rules (may be None)."""
        if self._nsfw_status_line:
            return self._nsfw_status_line
        try:
            from backend.behavior.nsfw_screen_scan import scan_status

            return str(scan_status().get("message") or "") or None
        except Exception:  # noqa: BLE001
            return None

    def _drain_extension_alerts(self) -> None:
        """Speak/soft-lock for alerts enqueued by SelfTracker extensions via API."""
        try:
            from backend.behavior.gate_alerts import drain_alerts, speak_alert

            pending = drain_alerts()
        except Exception as exc:  # noqa: BLE001
            log.debug("drain alerts: %s", exc)
            return
        for item in pending:
            kind = str(item.get("kind") or "default")
            msg = str(item.get("message") or "")
            detail = str(item.get("detail") or kind)
            if kind == "extension_tab_redirect":
                try:
                    from backend.behavior.tracker_block_gui import show_extension_redirect_notice

                    show_extension_redirect_notice(detail=detail)
                except Exception as exc:  # noqa: BLE001
                    log.debug("extension redirect notice: %s", exc)
                continue
            # API only enqueues now — tracker is the sole speaker for gate alerts.
            if msg:
                speak_alert(msg, force=False)
            if kind in (
                "goal_met",
                "threshold_alert",
            ):
                continue
            if kind in (
                "unauthorized_browser",
                "nsfw_screen",
                "porn",
                "keyword",
                "porn_or_keyword_block",
                "watch",
                "watch_site_block",
                "morning_bible",
                "morning_bible_required",
                "morning_plan",
                "morning_plan_required",
            ):
                # Soft-lock card only; skip second speak inside _soft_lock_notice
                now = time.time()
                if now - self._last_soft_lock_at < 20.0:
                    continue
                self._last_soft_lock_at = now
                try:
                    from backend.behavior.tracker_block_gui import show_nsfw_screen_notice

                    show_nsfw_screen_notice(
                        detail=detail,
                        gate=self._gate,
                        user_id=self._user_id,
                    )
                except Exception as exc:  # noqa: BLE001
                    log.debug("alert soft-lock: %s", exc)

    def _maybe_goals_alerts_if_due(self) -> None:
        """Check daily goal / threshold alerts (~once per minute)."""
        now = time.time()
        if (now - self._last_goals_check_at) < 60.0:
            return
        self._last_goals_check_at = now
        if not self._user_id:
            return
        try:
            from datetime import date

            from backend.behavior.goals_alerts import evaluate_and_fire
            from backend.db.base import SessionLocal
            from backend.models import User
            from backend.timetable.tracker_query import tracker_user_ids

            db = SessionLocal()
            try:
                user = db.query(User).filter(User.id == self._user_id).first()
                if not user:
                    return
                user_ids = tracker_user_ids(db, user)
                evaluate_and_fire(
                    db, user_ids, date.today(), user_id=self._user_id
                )
            finally:
                db.close()
        except Exception as exc:  # noqa: BLE001
            log.debug("goals alerts: %s", exc)

    def _maybe_away_prompt(self, idle_seconds: float) -> None:
        if not self._user_id or idle_seconds < 600.0:
            return
        try:
            from datetime import date

            from backend.behavior.goals_alerts import build_goals_status
            from backend.behavior.tracker_away_prompt import log_away_response, show_away_prompt
            from backend.db.base import SessionLocal
            from backend.models import User
            from backend.timetable.tracker_query import tracker_user_ids

            db = SessionLocal()
            try:
                user = db.query(User).filter(User.id == self._user_id).first()
                if not user:
                    return
                status = build_goals_status(
                    db, tracker_user_ids(db, user), date.today(), user_id=self._user_id
                )
                if status.get("goals") and status["goals"][0].get("met"):
                    return
            finally:
                db.close()

            def on_choice(choice: str) -> None:
                log_away_response(
                    choice=choice,
                    idle_seconds=idle_seconds,
                    user_id=self._user_id,
                )

            show_away_prompt(idle_seconds, on_choice=on_choice)
        except Exception as exc:  # noqa: BLE001
            log.debug("away prompt: %s", exc)

    def _poll_interval(self) -> float:
        """Poll faster while hard-block is locked so Steam games die quickly."""
        gate = self._gate or {}
        if gate.get("locked"):
            return min(0.75, float(self.config.poll_interval_s))
        return float(self.config.poll_interval_s)

    def flush_current(self, reason: str, *, end_at: float | None = None) -> None:
        with self._lock:
            if not self._current:
                return
            end = end_at if end_at is not None else time.time()
            ev = self._current.to_event(reason, end_at=end)
            if ev["duration_seconds"] >= 2 and self._user_id:
                # CSV immediately; SQLite via timed bulk flush
                enqueue_event(
                    self._user_id,
                    ev,
                    bulk_flush_s=self.config.bulk_flush_s,
                )
                try:
                    self._ws_queue.put_nowait(ev)
                except queue.Full:
                    pass
                log.info(
                    "[%s] %s  %ss  score=%d  %s",
                    reason,
                    self._current.exe,
                    ev["duration_seconds"],
                    ev["productivity_score"],
                    self._current.site,
                )
            self._current = None
            self._save_checkpoint(force=True)

    def _save_checkpoint(self, *, force: bool = False) -> None:
        now = time.time()
        min_gap = max(5.0, self.config.checkpoint_interval_s)
        if not force and (now - self._last_checkpoint_at) < min_gap:
            return
        cp = SessionCheckpoint(
            last_poll_at=self._last_poll_at,
            current=self._current.to_dict() if self._current else None,
        )
        cp.save()
        self._last_checkpoint_at = now

    def _recover_checkpoint(self) -> None:
        cp = SessionCheckpoint.load()
        if not cp:
            return
        age = time.time() - cp.last_poll_at
        if age > 86400:
            SessionCheckpoint().clear()
            return
        if cp.current and age < 86400:
            session = ActiveSession.from_dict(cp.current)
            end_at = cp.last_poll_at
            ev = session.to_event("recovery", end_at=end_at)
            if ev["duration_seconds"] >= 2 and self._user_id:
                persist_event(self._user_id, ev)
                log.info("[recovery] closed orphan session %s", session.exe)
        SessionCheckpoint().clear()

    def _handle_force_flush_request(self) -> None:
        if not consume_flush_request():
            return
        self.flush_current("force_sync")
        flush_pending_events()
        write_flush_ack()
        log.info("[force_sync] flushed on UI request")

    def _maybe_bulk_flush(self) -> None:
        now = time.time()
        if (now - self._last_bulk_tick_at) < max(5.0, self.config.bulk_flush_s):
            return
        self._last_bulk_tick_at = now
        flush_pending_events()

    def _poll_once(self) -> None:
        self._handle_force_flush_request()
        self._refresh_plan_if_due()
        self._refresh_gate_if_due()
        self._refresh_stack_health_if_due()
        self._maybe_bulk_flush()
        self._drain_extension_alerts()
        self._maybe_goals_alerts_if_due()
        self._maybe_nsfw_screen_scan()

        now = time.time()
        gap = now - self._last_poll_at
        if gap > self.config.sleep_gap_s and self._current:
            self.flush_current("sleep_gap", end_at=self._last_poll_at)

        idle_s = get_idle_seconds()
        if idle_s >= self.config.idle_threshold_s:
            if not self._was_idle:
                self._was_idle = True
                self._idle_since_at = now - idle_s
            if self._current:
                self.flush_current("idle", end_at=now - idle_s)
            self._last_poll_at = now
            self._save_checkpoint()
            return

        if self._was_idle:
            away_dur = now - (self._idle_since_at or now)
            self._was_idle = False
            self._idle_since_at = None
            self._maybe_away_prompt(away_dur)

        if self._paused.is_set():
            # Still enforce hard-block while "paused"
            if (self._gate_policy or {}).get("hard_block_enabled"):
                exe, title, pid = self._foreground()
                if exe:
                    self._maybe_hard_block(exe, title, pid)
                    self._maybe_unauthorized_browser(exe)
                    self._maybe_title_keyword_block(exe, title)
                    self._maybe_watch_title_leak(exe, title)
            self._last_poll_at = now
            self._save_checkpoint()
            return

        exe, title, pid = self._foreground()
        if not exe:
            self._last_poll_at = now
            self._save_checkpoint()
            return

        # Credit Bible minutes when Good News PDF is focused (no web app needed)
        if self._user_id:
            try:
                from backend.behavior.bible_desktop import credit_bible_if_reading

                credit_bible_if_reading(
                    self._user_id, exe, title, seconds=max(0.5, min(gap, 3.0))
                )
            except Exception:  # noqa: BLE001
                pass

        if is_ignored_app(exe, title):
            with self._lock:
                if self._current:
                    self.flush_current("app_switch", end_at=now)
            # Still kill games in background even if foreground is ignored (e.g. Steam helper)
            if (self._gate_policy or {}).get("hard_block_enabled"):
                self._maybe_hard_block(exe, title, pid)
            self._maybe_unauthorized_browser(exe)
            self._last_poll_at = now
            self._save_checkpoint()
            return

        if self._maybe_hard_block(exe, title, pid):
            self._last_poll_at = now
            self._save_checkpoint()
            return

        self._maybe_unauthorized_browser(exe)
        self._maybe_title_keyword_block(exe, title)
        self._maybe_watch_title_leak(exe, title)

        group_key, site = session_identity(exe, title)

        with self._lock:
            if self._current:
                self._current.latest_title = title
                self._current.title = title

            changed = self._current is None or self._current.group_key != group_key
            age = self._current.age() if self._current else 0
            flush = self._current is not None and (changed or age >= self.config.max_session_s)

            if flush and self._current:
                reason = "app_switch" if changed else "periodic_flush"
                end_at = now if changed else None
                self.flush_current(reason, end_at=end_at)

            if (changed or flush) and not self._paused.is_set():
                self._current = ActiveSession.start(exe, title, pid)

        self._last_poll_at = now
        self._save_checkpoint()

    def _poll_loop(self) -> None:
        log.info(
            "Poll loop started  interval=%.0fs  max_session=%.0fs  idle=%.0fs  bulk=%.0fs",
            self.config.poll_interval_s,
            self.config.max_session_s,
            self.config.idle_threshold_s,
            self.config.bulk_flush_s,
        )
        while not self._stop.is_set():
            try:
                self._poll_once()
            except Exception as exc:  # noqa: BLE001
                log.warning("Poll error: %s", exc)
            self._stop.wait(self._poll_interval())

    def start(self) -> None:
        enable_sqlite_wal()
        self._user_id = resolve_user_id(self.config)
        self._username = resolve_username(self._user_id)
        log.info(
            "Session user: %s (id=%s) — set TRACKER_USER_ID or %s to override",
            self._username,
            self._user_id,
            CONFIG_PATH,
        )
        log.info("Activity log: %s", tracker_log_path())
        self._plan_updated_at = 0.0
        self._gate_updated_at = 0.0
        self._refresh_plan_if_due()
        self._refresh_gate_if_due()
        self._recover_checkpoint()
        atexit.register(lambda: self.shutdown())
        self._stop.clear()
        self._thread = threading.Thread(target=self._poll_loop, name="tracker-poll", daemon=True)
        self._thread.start()
        self._start_ws_mirror()
        try:
            from backend.behavior.tracker_hub import start_tracker_hub

            start_tracker_hub()
        except Exception as exc:  # noqa: BLE001
            log.warning("Tracker hub start skipped: %s", exc)
        try:
            from backend.behavior.voice_agent import (
                start_voice_agent,
                sync_voice_with_browser_gate,
                voice_agent_enabled,
            )

            # Hotkey-only registration — never preloads Whisper/TTS/LLM.
            # First gate refresh may immediately pause if already FREE.
            if voice_agent_enabled():
                start_voice_agent(self._user_id, enable_hotkey=True)
                try:
                    sync_voice_with_browser_gate(
                        self.latest_gate(force=True), user_id=self._user_id
                    )
                except Exception as sync_exc:  # noqa: BLE001
                    log.debug("initial voice free-mode sync: %s", sync_exc)
            else:
                log.info(
                    "Voice agent skipped (VOICE_AGENT_ENABLED=0) — "
                    "tracker distraction tracking still active"
                )
        except Exception as exc:  # noqa: BLE001
            log.warning("Voice agent start skipped: %s", exc)

    def shutdown(self) -> None:
        if self._shutdown_done:
            return
        self._shutdown_done = True
        self._stop.set()
        try:
            from backend.behavior.voice_agent import stop_voice_agent

            stop_voice_agent()
        except Exception:  # noqa: BLE001
            pass
        try:
            from backend.behavior.tracker_hub import stop_tracker_hub

            stop_tracker_hub()
        except Exception:  # noqa: BLE001
            pass
        self.flush_current("shutdown")
        flush_pending_events()
        SessionCheckpoint().clear()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5)

    def _start_ws_mirror(self) -> None:
        import os

        ws_url = os.environ.get("BACKEND_WS_URL", "ws://localhost:8000/ws/behavior")
        token = os.environ.get("BACKEND_TOKEN", "")
        # Bind WS ingest to the same user as local SQLite writes (admin by default).
        if not token and self._user_id:
            try:
                from backend.core.auth import token_for
                from backend.db.base import SessionLocal
                from backend.models import User

                db = SessionLocal()
                try:
                    row = db.get(User, self._user_id)
                    if row:
                        token = token_for(row)
                finally:
                    db.close()
            except Exception as exc:  # noqa: BLE001
                log.debug("WS token mint skipped: %s", exc)

        def mirror() -> None:
            import asyncio

            async def drain_incoming(ws) -> None:
                """Process server pings and ack responses while send side is idle."""
                try:
                    while True:
                        await ws.recv()
                except Exception:
                    pass

            async def run() -> None:
                import websockets

                url = f"{ws_url}?token={token}" if token else ws_url
                while not self._stop.is_set():
                    try:
                        async with websockets.connect(
                            url,
                            ping_interval=None,
                            ping_timeout=None,
                            close_timeout=5,
                        ) as ws:
                            drain_task = asyncio.create_task(drain_incoming(ws))
                            try:
                                while not self._stop.is_set():
                                    try:
                                        ev = await asyncio.to_thread(self._ws_queue.get, True, 2)
                                    except queue.Empty:
                                        continue
                                    await ws.send(json.dumps(ev))
                            finally:
                                drain_task.cancel()
                                with contextlib.suppress(asyncio.CancelledError):
                                    await drain_task
                    except Exception as exc:
                        log.debug("WS mirror reconnecting: %s", exc)
                        await asyncio.sleep(5)

            try:
                asyncio.run(run())
            except Exception as exc:  # noqa: BLE001
                log.debug("WS mirror stopped: %s", exc)

        threading.Thread(target=mirror, name="tracker-ws", daemon=True).start()

    def ws_queue(self) -> queue.Queue[dict]:
        return self._ws_queue
