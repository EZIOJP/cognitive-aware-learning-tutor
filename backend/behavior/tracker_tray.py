"""System tray UI for standalone desktop tracker."""

from __future__ import annotations

import logging
import threading
import webbrowser
from typing import TYPE_CHECKING

from backend.behavior.time_fmt import format_hours_mins

log = logging.getLogger("desktop_tracker")
DASHBOARD_URL = "http://localhost:5173/productivity?tab=plan"
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
    return f"Plan now: {_truncate(b.title)} ({format_hours_mins(b.minutes_left)} left)"


def _fmt_plan_next(service: "TrackerService") -> str:
    ctx = service.plan_context()
    if ctx is None or ctx.next is None:
        return "Up next: —"
    b = ctx.next
    local = b.start_at.astimezone()
    return f"Up next: {_truncate(b.title)} · {local.strftime('%H:%M')}"


def _fmt_morning_next(service: "TrackerService") -> str:
    try:
        from backend.behavior.tracker_rules import next_step_label

        morning = (service.latest_gate() or {}).get("morning") or {}
        return f"Rules next: {next_step_label(morning.get('next'))}"
    except Exception:  # noqa: BLE001
        return "Rules next: ?"


def _fmt_browser_mode(service: "TrackerService") -> str:
    try:
        from backend.behavior.browser_gate_policy import mode_label

        browser = (service.latest_gate() or {}).get("browser") or {}
        mode = browser.get("mode") or (service.latest_gate() or {}).get("browser_mode")
        return f"Mode: {mode_label(str(mode or 'free'))}"
    except Exception:  # noqa: BLE001
        return "Mode: ?"


def _fmt_stack_health(_service: "TrackerService" | None = None) -> str:
    try:
        from backend.behavior.stack_health import get_stack_health

        return get_stack_health().status_line()
    except Exception:  # noqa: BLE001
        return "API: ? · Web: ?"


def _prompt_free_time() -> bool:
    """PIN/phrase then grant temporary free browsing (YouTube etc.)."""
    try:
        import tkinter as tk
        from tkinter import messagebox, simpledialog

        from backend.behavior.browser_gate_policy import (
            browser_free_after_hm,
            set_free_override,
        )
        from backend.behavior.tracker_exit import exit_prompt_hint, exit_secret_accepted
    except ImportError:
        return False

    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    try:
        typed = simpledialog.askstring(
            "CALT Tracker — Free time",
            exit_prompt_hint()
            + "\n\nGrants temporary free browsing (porn still blocked).\n"
            f"Evening free also starts at {browser_free_after_hm()} without PIN.",
            parent=root,
            show="*",
        )
        if not exit_secret_accepted(typed):
            return False
        until = set_free_override()
        messagebox.showinfo(
            "Free time",
            f"Free browsing until {until.strftime('%H:%M')} (local).\n"
            "Extensions pick this up within a few seconds.",
            parent=root,
        )
        return True
    finally:
        try:
            root.destroy()
        except tk.TclError:
            pass


def _fmt_reward_day(service: "TrackerService") -> str:
    try:
        from backend.behavior.reward_days import status

        st = status(int(service.user_id))
        if st.get("active_today"):
            return "Reward day: ACTIVE until midnight"
        n = int(st.get("available") or 0)
        return f"Reward day: {n} banked"
    except Exception:  # noqa: BLE001
        return "Reward day: ?"


def _tray_tooltip(service: "TrackerService") -> str:
    try:
        from backend.behavior.tracker_rules import format_tray_tooltip
        from backend.behavior.tracker_rules_gui import build_snapshot_from_service

        return format_tray_tooltip(build_snapshot_from_service(service))
    except Exception:  # noqa: BLE001
        return "CALT Tracker — right-click for menu"


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
        launch_transcript_studio,
        open_login_page,
        open_tracker_log,
    )
    from backend.behavior.tracker_reward_gui import show_reward_day_panel
    from backend.behavior.tracker_rules_gui import show_todays_rules_for_service
    from backend.behavior.tracker_schedule_gui import show_today_schedule_for_service

    def fmt_today() -> str:
        secs = service.today_seconds()
        return f"Today: {format_hours_mins(secs // 60)}"

    def make_icon() -> Image.Image:
        img = Image.new("RGB", (64, 64), color=(30, 41, 59))
        draw = ImageDraw.Draw(img)
        # Always "armed" — no tray Pause (hard-block stays strict).
        draw.ellipse((12, 12, 52, 52), fill=(52, 211, 153))
        return img

    def on_show_plan(_icon: pystray.Icon, _item: pystray.MenuItem) -> None:
        show_today_schedule_for_service(service)

    def on_show_rules(_icon: pystray.Icon, _item: pystray.MenuItem) -> None:
        show_todays_rules_for_service(service)

    def on_open_dashboard(_icon: pystray.Icon, _item: pystray.MenuItem) -> None:
        try:
            from backend.behavior.stack_health import open_calt_page

            open_calt_page("/productivity?tab=plan", speak=True, auto_start=True)
        except Exception:  # noqa: BLE001
            webbrowser.open(DASHBOARD_URL)

    def on_start_app(_icon: pystray.Icon, _item: pystray.MenuItem) -> None:
        try:
            from backend.behavior.stack_health import local_jarvis_speak, start_calt_stack

            local_jarvis_speak("stack_starting", force=True)
            start_calt_stack()
        except Exception as exc:  # noqa: BLE001
            log.warning("Start CALT stack failed: %s", exc)

    def on_start_studio(_icon: pystray.Icon, _item: pystray.MenuItem) -> None:
        launch_transcript_studio()

    def on_login(_icon: pystray.Icon, _item: pystray.MenuItem) -> None:
        open_login_page()

    def on_open_log(_icon: pystray.Icon, _item: pystray.MenuItem) -> None:
        open_tracker_log()

    def on_free_time(_icon: pystray.Icon, _item: pystray.MenuItem) -> None:
        if _prompt_free_time():
            log.info("Free-time override granted via tray")
            # Force next gate poll to see override soon
            try:
                service._gate_updated_at = 0  # noqa: SLF001
            except Exception:  # noqa: BLE001
                pass
        else:
            log.info("Free time cancelled — wrong PIN/phrase or dismissed")

    def on_reward_day(_icon: pystray.Icon, _item: pystray.MenuItem) -> None:
        def _bump_gate() -> None:
            try:
                service._gate_updated_at = 0  # noqa: SLF001
            except Exception:  # noqa: BLE001
                pass

        show_reward_day_panel(service, on_claimed=_bump_gate)

    def on_voice_agent(_icon: pystray.Icon, _item: pystray.MenuItem) -> None:
        try:
            from backend.behavior.voice_agent import open_voice_chat

            open_voice_chat(service.user_id)
        except Exception as exc:  # noqa: BLE001
            log.warning("Voice agent open failed: %s", exc)

    def on_toggle_voice_hotkey(_icon: pystray.Icon, _item: pystray.MenuItem) -> None:
        """Gaming toggle: stop PTT listener + release STT; tracker stays up."""
        try:
            from backend.behavior.voice_agent import (
                is_voice_hotkey_enabled,
                set_voice_hotkey_enabled,
            )

            want = not is_voice_hotkey_enabled()
            set_voice_hotkey_enabled(want, user_id=service.user_id)
        except Exception as exc:  # noqa: BLE001
            log.warning("Voice hotkey toggle failed: %s", exc)

    def _voice_hotkey_label(_item: pystray.MenuItem | None = None) -> str:
        try:
            from backend.behavior.voice_agent import (
                is_free_mode_paused,
                is_voice_hotkey_enabled,
                voice_agent_enabled,
            )

            if not voice_agent_enabled():
                return "Voice hotkey: OFF (env)"
            if is_free_mode_paused():
                return "Voice hotkey: OFF (free mode)"
            return (
                "Voice hotkey: ON"
                if is_voice_hotkey_enabled()
                else "Voice hotkey: OFF (gaming)"
            )
        except Exception:  # noqa: BLE001
            return "Voice hotkey: ?"

    def build_menu() -> pystray.Menu:
        return pystray.Menu(
            pystray.MenuItem(lambda _i: "Status: Running (no pause)", None, enabled=False),
            pystray.MenuItem(lambda _i: f"User: {service.username}", None, enabled=False),
            pystray.MenuItem(lambda _i: fmt_today(), None, enabled=False),
            pystray.MenuItem(lambda _i: _fmt_browser_mode(service), None, enabled=False),
            pystray.MenuItem(lambda _i: _fmt_reward_day(service), None, enabled=False),
            pystray.MenuItem(lambda _i: _fmt_morning_next(service), None, enabled=False),
            pystray.MenuItem(lambda _i: _fmt_stack_health(), None, enabled=False),
            pystray.MenuItem(lambda _i: _fmt_plan_now(service), None, enabled=False),
            pystray.MenuItem(lambda _i: _fmt_plan_next(service), None, enabled=False),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Today's rules", on_show_rules),
            pystray.MenuItem("Show today's plan", on_show_plan, default=True),
            pystray.MenuItem("Free time…", on_free_time),
            pystray.MenuItem("Reward day…", on_reward_day),
            pystray.MenuItem("Voice agent (chat)", on_voice_agent),
            pystray.MenuItem(_voice_hotkey_label, on_toggle_voice_hotkey),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Start CALT stack", on_start_app),
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
        _tray_tooltip(service),
        menu=build_menu(),
    )

    def _refresh_tooltip() -> None:
        """Keep tray hover text current with stack health (API/Web)."""
        import time as _time

        while not service._stop.is_set():  # noqa: SLF001
            try:
                icon.title = _tray_tooltip(service)
            except Exception:  # noqa: BLE001
                pass
            _time.sleep(20)

    threading.Thread(
        target=_refresh_tooltip,
        daemon=True,
        name="tray-tooltip-refresh",
    ).start()

    log.info("System tray icon active (pause disabled)")
    icon.run()


def run_headless_loop(service: "TrackerService") -> None:
    """Background only — no tray icon. Stop via scripts\\admin_only\\stop_desktop_tracker.bat (PIN)."""
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
