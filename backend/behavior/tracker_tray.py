"""System tray UI for standalone desktop tracker."""

from __future__ import annotations

import logging
import webbrowser
from typing import TYPE_CHECKING

log = logging.getLogger("desktop_tracker")

DASHBOARD_URL = "http://localhost:5173/productivity"
LOGIN_URL = "http://localhost:5173/login"


def _truncate(text: str, max_len: int = 38) -> str:
    text = text.strip()
    if len(text) <= max_len:
        return text
    return text[: max_len - 1] + "…"


def _fmt_plan_now(service: "TrackerService") -> str:
    ctx = service.plan_context()
    if ctx is None or ctx.current is None:
        return "Plan now: — none —"
    b = ctx.current
    return f"Plan now: {_truncate(b.title)} ({b.minutes_left}m left)"


def _fmt_plan_next(service: "TrackerService") -> str:
    ctx = service.plan_context()
    if ctx is None or ctx.next is None:
        return "Up next: —"
    b = ctx.next
    local = b.start_at.astimezone()
    return f"Up next: {_truncate(b.title)} · {local.strftime('%H:%M')}"


def run_tray(service: "TrackerService") -> None:
    """Block on system tray (main thread). Requires pystray + Pillow."""
    try:
        import pystray
        from PIL import Image, ImageDraw
    except ImportError as exc:
        log.error("Tray requires pystray and Pillow: %s", exc)
        _run_headless_wait(service)
        return

    from backend.behavior.tracker_launchers import (
        launch_app_fe_be,
        launch_transcript_studio,
        open_login_page,
        open_tracker_log,
    )
    from backend.behavior.tracker_schedule_gui import show_today_schedule_for_service

    def fmt_today() -> str:
        secs = service.today_seconds()
        m = secs // 60
        if m < 60:
            return f"Today: {m}m"
        h, rem = divmod(m, 60)
        return f"Today: {h}h {rem}m" if rem else f"Today: {h}h"

    def make_icon() -> Image.Image:
        img = Image.new("RGB", (64, 64), color=(30, 41, 59))
        draw = ImageDraw.Draw(img)
        # Always "armed" — no tray Pause (hard-block stays strict).
        draw.ellipse((12, 12, 52, 52), fill=(52, 211, 153))
        return img

    def on_show_plan(_icon: pystray.Icon, _item: pystray.MenuItem) -> None:
        show_today_schedule_for_service(service)

    def on_open_dashboard(_icon: pystray.Icon, _item: pystray.MenuItem) -> None:
        webbrowser.open(DASHBOARD_URL)

    def on_start_app(_icon: pystray.Icon, _item: pystray.MenuItem) -> None:
        launch_app_fe_be()

    def on_start_studio(_icon: pystray.Icon, _item: pystray.MenuItem) -> None:
        launch_transcript_studio()

    def on_login(_icon: pystray.Icon, _item: pystray.MenuItem) -> None:
        open_login_page()

    def on_open_log(_icon: pystray.Icon, _item: pystray.MenuItem) -> None:
        open_tracker_log()

    def build_menu() -> pystray.Menu:
        return pystray.Menu(
            pystray.MenuItem(lambda _i: "Status: Running (no pause)", None, enabled=False),
            pystray.MenuItem(lambda _i: f"User: {service.username}", None, enabled=False),
            pystray.MenuItem(lambda _i: fmt_today(), None, enabled=False),
            pystray.MenuItem(lambda _i: _fmt_plan_now(service), None, enabled=False),
            pystray.MenuItem(lambda _i: _fmt_plan_next(service), None, enabled=False),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Show today's plan", on_show_plan, default=True),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Start API + frontend", on_start_app),
            pystray.MenuItem("Transcript Notes Studio", on_start_studio),
            pystray.MenuItem("Open login (web app)", on_login),
            pystray.MenuItem("Open full calendar", on_open_dashboard),
            pystray.MenuItem("View tracker log", on_open_log),
        )

    # Ensure pause cannot stick from an older build
    if service.paused:
        service.set_paused(False)

    icon = pystray.Icon(
        "calt_tracker",
        make_icon(),
        "CALT Tracker — right-click for menu",
        menu=build_menu(),
    )
    log.info("System tray icon active (pause disabled)")
    icon.run()


def run_headless_loop(service: "TrackerService") -> None:
    """Background only — no tray icon. Stop via scripts\\desktop_tracker\\stop_desktop_tracker.bat."""
    import time

    try:
        while not service._stop.is_set():  # noqa: SLF001
            time.sleep(1)
    except KeyboardInterrupt:
        service.shutdown()


def _run_headless_wait(service: "TrackerService") -> None:
    """Fallback when pystray/Pillow missing."""
    run_headless_loop(service)


if TYPE_CHECKING:
    from backend.behavior.tracker_service import TrackerService
