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
        return {
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

    @property
    def paused(self) -> bool:
        return self._paused.is_set()

    def set_paused(self, value: bool) -> None:
        if value:
            self._paused.set()
            self.flush_current("pause")
        else:
            self._paused.clear()

    def today_seconds(self) -> int:
        if not self._user_id:
            return 0
        return today_total_seconds(self._user_id)

    def plan_context(self) -> PlanContext | None:
        return self._plan_context

    @property
    def user_id(self) -> int:
        return self._user_id

    @property
    def username(self) -> str:
        return self._username or (f"user#{self._user_id}" if self._user_id else "—")

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

    def flush_current(self, reason: str, *, end_at: float | None = None) -> None:
        with self._lock:
            if not self._current:
                return
            end = end_at if end_at is not None else time.time()
            ev = self._current.to_event(reason, end_at=end)
            if ev["duration_seconds"] >= 2 and self._user_id:
                persist_event(self._user_id, ev)
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
            self._save_checkpoint()

    def _save_checkpoint(self) -> None:
        cp = SessionCheckpoint(
            last_poll_at=self._last_poll_at,
            current=self._current.to_dict() if self._current else None,
        )
        cp.save()

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
        write_flush_ack()
        log.info("[force_sync] flushed on UI request")

    def _poll_once(self) -> None:
        self._handle_force_flush_request()
        self._refresh_plan_if_due()

        now = time.time()
        gap = now - self._last_poll_at
        if gap > self.config.sleep_gap_s and self._current:
            self.flush_current("sleep_gap", end_at=self._last_poll_at)

        idle_s = get_idle_seconds()
        if idle_s >= self.config.idle_threshold_s:
            if self._current:
                self.flush_current("idle", end_at=now - idle_s)
            self._last_poll_at = now
            self._save_checkpoint()
            return

        if self._paused.is_set():
            self._last_poll_at = now
            self._save_checkpoint()
            return

        exe, title, pid = self._foreground()
        if not exe:
            self._last_poll_at = now
            self._save_checkpoint()
            return

        if is_ignored_app(exe, title):
            with self._lock:
                if self._current:
                    self.flush_current("app_switch", end_at=now)
            self._last_poll_at = now
            self._save_checkpoint()
            return

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
            "Poll loop started  interval=%.0fs  max_session=%.0fs  idle=%.0fs",
            self.config.poll_interval_s,
            self.config.max_session_s,
            self.config.idle_threshold_s,
        )
        while not self._stop.is_set():
            try:
                self._poll_once()
            except Exception as exc:  # noqa: BLE001
                log.warning("Poll error: %s", exc)
            self._stop.wait(self.config.poll_interval_s)

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
        self._refresh_plan_if_due()
        self._recover_checkpoint()
        atexit.register(lambda: self.shutdown())
        self._stop.clear()
        self._thread = threading.Thread(target=self._poll_loop, name="tracker-poll", daemon=True)
        self._thread.start()
        self._start_ws_mirror()

    def shutdown(self) -> None:
        if self._shutdown_done:
            return
        self._shutdown_done = True
        self._stop.set()
        self.flush_current("shutdown")
        SessionCheckpoint().clear()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5)

    def _start_ws_mirror(self) -> None:
        import os

        ws_url = os.environ.get("BACKEND_WS_URL", "ws://localhost:8000/ws/behavior")
        token = os.environ.get("BACKEND_TOKEN", "")

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
