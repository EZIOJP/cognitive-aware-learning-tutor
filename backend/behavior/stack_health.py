"""Light HTTP probes for CALT API (:8000) and Vite frontend (:5173).

Hub (:8765) is intentionally separate — do not treat hub /health as API up.

Tracker owns start-stack + redirect + local Jarvis speaks (no FastAPI/Vite required for TTS).
"""

from __future__ import annotations

import logging
import os
import subprocess
import threading
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Literal

log = logging.getLogger("desktop_tracker.stack_health")

PROBE_INTERVAL_S = float(os.environ.get("CALT_STACK_PROBE_INTERVAL_S", "20") or "20")
PROBE_TIMEOUT_S = float(os.environ.get("CALT_STACK_PROBE_TIMEOUT_S", "1.5") or "1.5")
JARVIS_DOWN_COOLDOWN_S = float(os.environ.get("CALT_STACK_JARVIS_COOLDOWN_S", "300") or "300")
STACK_WAIT_TIMEOUT_S = float(os.environ.get("CALT_STACK_WAIT_TIMEOUT_S", "120") or "120")
STACK_WAIT_POLL_S = float(os.environ.get("CALT_STACK_WAIT_POLL_S", "2.5") or "2.5")

_lock = threading.Lock()
_cached_at: float = 0.0
_prev_api: bool | None = None
_prev_web: bool | None = None
_pending_down_kinds: set[str] = set()
_last_jarvis_at: float = 0.0

OpenAction = Literal["open", "warn_api_open", "offer_start", "blocked"]


@dataclass(frozen=True)
class StackHealth:
    api_up: bool
    web_up: bool

    def status_line(self) -> str:
        api = "up" if self.api_up else "down"
        web = "up" if self.web_up else "down"
        return f"API: {api} · Web: {web}"

    def short_bits(self) -> str:
        """Compact for tray tooltip."""
        return f"API:{'up' if self.api_up else 'dn'} · Web:{'up' if self.web_up else 'dn'}"


@dataclass(frozen=True)
class DownDialogSpec:
    """Pure description of the stack-down dialog (no Tk)."""

    title: str
    body: str
    primary: str = "Start CALT stack"
    secondary: str = "Cancel"
    kind: str = "web"  # web | api | both


_cached: StackHealth | None = None


def api_base_url() -> str:
    raw = (
        os.environ.get("CALT_API_URL")
        or os.environ.get("BACKEND_URL")
        or os.environ.get("VITE_API_BASE")
        or "http://127.0.0.1:8000"
    ).strip().rstrip("/")
    # VITE_API_BASE may end with /api/vocab — strip path to origin
    if "/api/" in raw:
        raw = raw.split("/api/")[0].rstrip("/")
    return raw or "http://127.0.0.1:8000"


def api_health_url() -> str:
    return f"{api_base_url()}/health"


def frontend_url() -> str:
    raw = (
        os.environ.get("CALT_FRONTEND_URL")
        or os.environ.get("VITE_DEV_SERVER_URL")
        or "http://127.0.0.1:5173"
    ).strip().rstrip("/")
    return raw or "http://127.0.0.1:5173"


def resolve_app_url(path_or_url: str) -> str:
    """Join relative paths to configured frontend origin; leave absolute URLs alone."""
    raw = (path_or_url or "").strip()
    if not raw:
        return frontend_url() + "/"
    if raw.startswith("http://") or raw.startswith("https://"):
        return raw
    base = frontend_url().rstrip("/")
    if not raw.startswith("/"):
        raw = "/" + raw
    return base + raw


def probe_url(url: str, *, timeout: float | None = None, method: str = "GET") -> bool:
    """Return True if HTTP response status is 2xx/3xx. Never raises."""
    t = PROBE_TIMEOUT_S if timeout is None else float(timeout)
    try:
        req = urllib.request.Request(url, method=method.upper())
        with urllib.request.urlopen(req, timeout=t) as resp:  # noqa: S310 — local health only
            code = int(getattr(resp, "status", None) or resp.getcode() or 0)
            return 200 <= code < 400
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
        log.debug("probe %s failed: %s", url, exc)
        return False
    except Exception as exc:  # noqa: BLE001
        log.debug("probe %s unexpected: %s", url, exc)
        return False


def probe_stack(*, timeout: float | None = None) -> StackHealth:
    """Probe API /health and frontend root. Does not touch hub :8765."""
    api = probe_url(api_health_url(), timeout=timeout, method="GET")
    # Prefer HEAD for Vite; fall back to GET if HEAD rejected
    fe = frontend_url() + "/"
    web = probe_url(fe, timeout=timeout, method="HEAD")
    if not web:
        web = probe_url(fe, timeout=timeout, method="GET")
    return StackHealth(api_up=api, web_up=web)


def _apply_probe_result(snap: StackHealth, *, now: float | None = None) -> StackHealth:
    """Update cache + transition flags. Used by get_stack_health and tests."""
    global _cached, _cached_at, _prev_api, _prev_web, _pending_down_kinds

    t = time.monotonic() if now is None else float(now)
    with _lock:
        if _prev_api is True and not snap.api_up:
            _pending_down_kinds.add("api")
        if _prev_web is True and not snap.web_up:
            _pending_down_kinds.add("web")
        _prev_api = snap.api_up
        _prev_web = snap.web_up
        _cached = snap
        _cached_at = t
    return snap


def get_stack_health(*, force: bool = False) -> StackHealth:
    """Cached probe (default ~20s). Safe to call from UI poll / tray tooltip."""
    global _cached, _cached_at
    now = time.monotonic()
    with _lock:
        age_ok = _cached is not None and (now - _cached_at) < PROBE_INTERVAL_S
        if not force and age_ok:
            return _cached  # type: ignore[return-value]

    snap = probe_stack()
    return _apply_probe_result(snap, now=now)


def resolve_open_action(health: StackHealth, *, offer_start: bool = True) -> OpenAction:
    """Pure: decide what open_app_page_guard should do."""
    if health.web_up and health.api_up:
        return "open"
    if health.web_up and not health.api_up:
        return "warn_api_open"
    if offer_start:
        return "offer_start"
    return "blocked"


def down_dialog_spec(health: StackHealth, *, target_hint: str = "") -> DownDialogSpec:
    """Pure copy for Web/API down dialogs (Start + Cancel)."""
    fe = frontend_url()
    api = api_base_url()
    hint = f"\n\nTarget after start: {target_hint}" if target_hint else ""
    if not health.web_up and not health.api_up:
        return DownDialogSpec(
            title="CALT stack is down",
            body=(
                f"API ({api}) and Web UI ({fe}) are not responding.\n\n"
                "Opening a page now would show a blank browser.\n\n"
                "Start CALT stack launches run.bat (API + Vite), waits until "
                f"the Web UI is up, then opens the page.{hint}"
            ),
            kind="both",
        )
    if not health.web_up:
        return DownDialogSpec(
            title="CALT Web UI is down",
            body=(
                f"Frontend is not responding on {fe}.\n\n"
                "Opening the page now would show an empty/blank browser.\n\n"
                "Start CALT stack launches run.bat (API + Vite), waits until "
                f"Vite is up, then opens the page.{hint}"
            ),
            kind="web",
        )
    return DownDialogSpec(
        title="CALT API is down",
        body=(
            f"Frontend is up, but the API is not responding on {api}.\n\n"
            "Gate / Bible / plan data may be stale or empty.\n\n"
            "You can open the page anyway, or Start CALT stack to bring "
            f"FastAPI back.{hint}"
        ),
        kind="api",
        primary="Start CALT stack",
        secondary="Open anyway",
    )


def jarvis_category_for_down(kind: str) -> str:
    """Map down-dialog kind → dialogues category."""
    k = (kind or "").strip().lower()
    if k == "both":
        return "stack_both_down"
    if k == "api":
        return "stack_api_down"
    return "stack_web_down"


def maybe_jarvis_stack_down_line() -> str | None:
    """One rate-limited canned line when API and/or Web just transitioned to down."""
    global _last_jarvis_at, _pending_down_kinds

    with _lock:
        kinds = set(_pending_down_kinds)
        if not kinds:
            return None
        now = time.monotonic()
        if _last_jarvis_at and (now - _last_jarvis_at) < JARVIS_DOWN_COOLDOWN_S:
            return None
        _pending_down_kinds.clear()
        _last_jarvis_at = now

    if kinds >= {"api", "web"} or kinds == {"api", "web"}:
        return "API and Web are down — Start CALT stack from the tray, or run run.bat."
    if "api" in kinds:
        return "API is down — gate/data may be stale until FastAPI is back on :8000."
    if "web" in kinds:
        return "Web UI is down — pages will be blank until Vite is on :5173."
    return None


def local_jarvis_speak(category: str, *, force: bool = True, **fmt: object) -> str:
    """Tracker-local canned speak + surface text. Never needs FastAPI/Vite."""
    try:
        from backend.behavior.voice_agent import dialogues as dlg

        return dlg.speak(category, force=force, **fmt)
    except Exception as exc:  # noqa: BLE001
        log.debug("local jarvis speak failed: %s", exc)
        return ""


def open_url_preferred(url: str) -> bool:
    """Open *url* in Edge → default browser. Returns True if something launched."""
    url = resolve_app_url(url)
    if not url:
        return False
    candidates: list[Path] = []
    prog = os.environ.get("ProgramFiles", r"C:\Program Files")
    prog86 = os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")
    candidates += [
        Path(prog) / "Microsoft" / "Edge" / "Application" / "msedge.exe",
        Path(prog86) / "Microsoft" / "Edge" / "Application" / "msedge.exe",
    ]
    for exe in candidates:
        if exe.is_file():
            try:
                subprocess.Popen(  # noqa: S603
                    [str(exe), url],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                log.info("Opened %s via %s", url, exe.name)
                return True
            except OSError as exc:
                log.debug("preferred browser %s failed: %s", exe, exc)
    try:
        import webbrowser

        webbrowser.open(url)
        log.info("Opened %s via default browser", url)
        return True
    except Exception as exc:  # noqa: BLE001
        log.warning("Could not open %s: %s", url, exc)
        return False


def wait_for_stack(
    *,
    want_web: bool = True,
    want_api: bool = False,
    timeout_s: float | None = None,
    poll_s: float | None = None,
    on_tick: Callable[[StackHealth], None] | None = None,
) -> StackHealth | None:
    """Poll until requirements met. Returns final health, or None on timeout."""
    deadline = time.monotonic() + float(
        STACK_WAIT_TIMEOUT_S if timeout_s is None else timeout_s
    )
    interval = float(STACK_WAIT_POLL_S if poll_s is None else poll_s)
    last: StackHealth | None = None
    while time.monotonic() < deadline:
        last = probe_stack(timeout=min(PROBE_TIMEOUT_S, interval))
        _apply_probe_result(last)
        if on_tick:
            try:
                on_tick(last)
            except Exception:  # noqa: BLE001
                pass
        ok_web = (not want_web) or last.web_up
        ok_api = (not want_api) or last.api_up
        if ok_web and ok_api:
            return last
        time.sleep(max(0.4, interval))
    return last


_open_debounce_lock = threading.Lock()
_last_open_url = ""
_last_open_mono = 0.0
OPEN_DEBOUNCE_S = float(os.environ.get("CALT_OPEN_DEBOUNCE_S", "15") or "15")


def start_calt_stack(*, force: bool = False) -> bool:
    """Launch run.bat only when Web is down (unless *force*).

    Returns True if a launch was attempted, False if skipped (already up).
    """
    from backend.behavior.tracker_launchers import launch_calt_stack

    if not force:
        snap = get_stack_health(force=True)
        if snap.web_up:
            log.info("start_calt_stack skipped — Web already up")
            return False
    launch_calt_stack()
    return True


def open_or_focus_calt(path_or_url: str, *, force: bool = False) -> bool:
    """Prefer extension FOCUS (one tab); debounce duplicate opens; fallback browser."""
    global _last_open_url, _last_open_mono
    target = resolve_app_url(path_or_url)
    now = time.monotonic()
    with _open_debounce_lock:
        if (
            not force
            and target == _last_open_url
            and (now - _last_open_mono) < OPEN_DEBOUNCE_S
        ):
            log.info("open_or_focus_calt debounced: %s", target)
            return True
        _last_open_url = target
        _last_open_mono = now

    # Queue for SelfTracker (polls API or hub)
    try:
        from backend.behavior import calt_tab_command as ctc

        path = path_or_url if path_or_url.startswith("/") else target
        if target.startswith(frontend_url()):
            path = target[len(frontend_url().rstrip("/")) :] or "/"
            if not path.startswith("/"):
                path = "/" + path
        ctc.request_focus(path if path_or_url.startswith("/") else path, force=force)
    except Exception as exc:  # noqa: BLE001
        log.debug("calt tab command queue failed: %s", exc)

    # Still open once via preferred browser (extension will consolidate tabs)
    return open_url_preferred(target)


def start_stack_then_open(
    url: str,
    *,
    want_web: bool = True,
    want_api: bool = False,
    on_message: Callable[[str, str], None] | None = None,
    on_status: Callable[[str], None] | None = None,
    speak: bool = True,
) -> bool:
    """Launch stack if needed, poll until ready, open *url*. Returns True if opened.

    *on_status* is for brief non-modal updates (e.g. window title).
    *on_message* is for failures / still-waiting dialogs.
    """
    notify = on_message or (lambda _t, _b: None)
    status = on_status or (lambda _s: None)
    target = resolve_app_url(url)

    snap0 = get_stack_health(force=True)
    if snap0.web_up:
        status("Opening…")
        ok = open_or_focus_calt(target)
        status("")
        return ok

    status("Starting CALT stack…")
    if speak:
        local_jarvis_speak("stack_starting", force=True)
    try:
        start_calt_stack()
    except Exception as exc:  # noqa: BLE001
        status("")
        notify("Start failed", f"Could not launch run.bat:\n{exc}")
        return False

    status("Waiting for Web UI…")
    snap = wait_for_stack(want_web=want_web, want_api=want_api)
    if snap is None or (want_web and not snap.web_up):
        status("")
        notify(
            "Still waiting",
            "CALT stack was launched, but the Web UI is not up yet.\n"
            f"Check the run.bat console, then try again.\n\nTarget: {target}",
        )
        return False
    if speak:
        local_jarvis_speak("stack_ready", force=True)
    status("Opening…")
    ok = open_or_focus_calt(target, force=True)
    status("")
    return ok


def open_calt_page(
    path_or_url: str,
    *,
    health: StackHealth | None = None,
    on_message: Callable[[str, str], None] | None = None,
    on_status: Callable[[str], None] | None = None,
    parent: object | None = None,
    speak: bool = True,
    auto_start: bool = True,
) -> bool:
    """Open a CALT app page — primary helper for Open Bible / Productivity / login.

    If the Web UI is up → focus/open one tab (debounced).
    If Web is down and *auto_start* → launch run.bat only then, poll, open.
    Never launches run.bat when Web is already up.

    Returns True if a browser open was attempted (or debounced as success).
    """
    target = resolve_app_url(path_or_url)
    snap = health if health is not None else get_stack_health(force=True)
    notify = on_message or (lambda _t, _b: None)

    if snap.web_up:
        if not snap.api_up and speak:
            local_jarvis_speak(jarvis_category_for_down("api"), force=False)
        return open_or_focus_calt(target)

    if not auto_start:
        return open_app_page_guard(
            target,
            health=snap,
            on_message=notify,
            parent=parent,
            offer_start=True,
            speak=speak,
        )

    return start_stack_then_open(
        target,
        want_web=True,
        want_api=False,
        on_message=notify,
        on_status=on_status,
        speak=speak,
    )


def _tk_ask_start(spec: DownDialogSpec, *, parent: object | None = None) -> bool | None:
    """Show Start / Cancel (or Open anyway for API-only). None = dialog unavailable.

    Returns True → primary (Start), False → secondary/cancel.
    """
    try:
        import tkinter as tk
        from tkinter import messagebox
    except ImportError:
        return None

    # Prefer custom buttons labeled Start / Cancel
    root: tk.Tk | None = None
    owned = False
    try:
        if parent is not None:
            dlg_parent = parent
        else:
            root = tk.Tk()
            root.withdraw()
            try:
                root.attributes("-topmost", True)
            except tk.TclError:
                pass
            dlg_parent = root
            owned = True

        result: dict[str, bool | None] = {"v": None}

        win = tk.Toplevel(dlg_parent)  # type: ignore[arg-type]
        win.title(spec.title)
        win.configure(bg="#0f172a")
        win.resizable(False, False)
        try:
            win.attributes("-topmost", True)
            win.transient(dlg_parent)  # type: ignore[arg-type]
        except tk.TclError:
            pass

        tk.Label(
            win,
            text=spec.title,
            bg="#0f172a",
            fg="#f8fafc",
            font=("Segoe UI", 11, "bold"),
            wraplength=420,
            justify=tk.LEFT,
        ).pack(anchor=tk.W, padx=16, pady=(14, 6))
        tk.Label(
            win,
            text=spec.body,
            bg="#0f172a",
            fg="#cbd5e1",
            font=("Segoe UI", 9),
            wraplength=420,
            justify=tk.LEFT,
        ).pack(anchor=tk.W, padx=16, pady=(0, 12))

        row = tk.Frame(win, bg="#0f172a")
        row.pack(fill=tk.X, padx=16, pady=(0, 14))

        def choose(v: bool) -> None:
            result["v"] = v
            try:
                win.destroy()
            except tk.TclError:
                pass

        tk.Button(
            row,
            text=spec.primary,
            command=lambda: choose(True),
            bg="#0d9488",
            fg="#f0fdfa",
            activebackground="#14b8a6",
            relief=tk.FLAT,
            padx=14,
            pady=7,
            cursor="hand2",
            font=("Segoe UI", 9, "bold"),
        ).pack(side=tk.RIGHT, padx=(8, 0))
        tk.Button(
            row,
            text=spec.secondary,
            command=lambda: choose(False),
            bg="#334155",
            fg="#e2e8f0",
            activebackground="#475569",
            relief=tk.FLAT,
            padx=12,
            pady=7,
            cursor="hand2",
            font=("Segoe UI", 9),
        ).pack(side=tk.RIGHT)

        win.protocol("WM_DELETE_WINDOW", lambda: choose(False))
        win.grab_set()
        win.focus_force()
        win.wait_window()
        return bool(result["v"]) if result["v"] is not None else False
    except Exception as exc:  # noqa: BLE001
        log.debug("custom start dialog failed, fallback askyesno: %s", exc)
        try:
            return bool(
                messagebox.askyesno(
                    spec.title,
                    spec.body + f"\n\n{spec.primary}?",
                    parent=parent,
                )
            )
        except Exception:  # noqa: BLE001
            return None
    finally:
        if owned and root is not None:
            try:
                root.destroy()
            except tk.TclError:
                pass


def open_app_page_guard(
    url: str,
    *,
    health: StackHealth | None = None,
    on_message: Callable[[str, str], None] | None = None,
    on_offer_start: Callable[[DownDialogSpec], bool] | None = None,
    parent: object | None = None,
    offer_start: bool = True,
    speak: bool = True,
) -> bool:
    """Open *url* if frontend is up; otherwise offer Start CALT stack then redirect.

    Prefer :func:`open_calt_page` for Open Bible / Productivity CTAs (auto-starts
    without a second click). This guard keeps the Start/Cancel dialog path.

    *on_offer_start(spec)* → True to start+poll+open. If omitted and offer_start,
    shows a Tk Start/Cancel dialog.
    *on_message(title, body)* — informational (API warn / still waiting).
    Returns True if a browser was opened.
    """
    target = resolve_app_url(url)
    snap = health if health is not None else get_stack_health(force=True)
    notify = on_message or (lambda _t, _b: None)
    action = resolve_open_action(snap, offer_start=offer_start)

    if action == "open":
        return open_url_preferred(target)

    if action == "warn_api_open":
        spec = down_dialog_spec(snap, target_hint=target)
        if speak:
            local_jarvis_speak(jarvis_category_for_down(spec.kind), force=True)
        # API-only down: offer Start, else open anyway
        ask = on_offer_start
        if ask is None and offer_start:
            ask = lambda s: bool(_tk_ask_start(s, parent=parent))  # noqa: E731
        if ask is not None:
            try:
                if ask(spec):
                    return start_stack_then_open(
                        target, want_web=True, want_api=True, on_message=notify, speak=speak
                    )
            except Exception as exc:  # noqa: BLE001
                log.debug("api-down offer_start failed: %s", exc)
        notify(spec.title, spec.body)
        return open_url_preferred(target)

    if action == "blocked":
        spec = down_dialog_spec(snap, target_hint=target)
        if speak:
            local_jarvis_speak(jarvis_category_for_down(spec.kind), force=True)
        notify(spec.title, spec.body)
        return False

    # offer_start — web down
    spec = down_dialog_spec(snap, target_hint=target)
    if speak:
        local_jarvis_speak(jarvis_category_for_down(spec.kind), force=True)

    ask = on_offer_start
    if ask is None:
        ask = lambda s: bool(_tk_ask_start(s, parent=parent))  # noqa: E731

    try:
        want = bool(ask(spec))
    except Exception as exc:  # noqa: BLE001
        log.debug("offer_start failed: %s", exc)
        notify(spec.title, spec.body)
        return False

    if not want:
        return False
    return start_stack_then_open(
        target, want_web=True, want_api=False, on_message=notify, speak=speak
    )


def reset_cache_for_tests() -> None:
    global _cached, _cached_at, _prev_api, _prev_web, _pending_down_kinds, _last_jarvis_at
    global _last_open_url, _last_open_mono
    with _lock:
        _cached = None
        _cached_at = 0.0
        _prev_api = None
        _prev_web = None
        _pending_down_kinds = set()
        _last_jarvis_at = 0.0
    with _open_debounce_lock:
        _last_open_url = ""
        _last_open_mono = 0.0
