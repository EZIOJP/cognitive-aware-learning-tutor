"""Popup when hard-block kills a game — points to /bible chapter reader (no PDF)."""

from __future__ import annotations

import logging
import threading
import tkinter as tk
from typing import Any

log = logging.getLogger("desktop_tracker")
_window_lock = threading.Lock()
_window: tk.Tk | None = None
_last_show_at = 0.0
_MIN_GAP_S = 45.0
_BIBLE_URL = "http://localhost:5173/bible"
_PLAN_URL = "http://localhost:5173/productivity?tab=plan"


def _target_bible_url() -> str:
    try:
        from backend.behavior.stack_health import frontend_url, resolve_app_url

        return resolve_app_url("/bible") if frontend_url() else _BIBLE_URL
    except Exception:  # noqa: BLE001
        return _BIBLE_URL


def _target_plan_url() -> str:
    try:
        from backend.behavior.stack_health import resolve_app_url

        return resolve_app_url("/productivity?tab=plan")
    except Exception:  # noqa: BLE001
        return _PLAN_URL


def _fmt_minutes(m: float | int) -> str:
    from backend.behavior.time_fmt import format_hours_mins

    return format_hours_mins(m)


def _draw_ring(canvas: tk.Canvas, done: int, goal: int) -> None:
    canvas.delete("all")
    w = int(canvas["width"])
    h = int(canvas["height"])
    pad = 8
    x0, y0, x1, y1 = pad, pad, w - pad, h - pad
    canvas.create_oval(x0, y0, x1, y1, outline="#334155", width=10)
    goal = max(1, goal)
    frac = min(1.0, max(0.0, done / goal))
    extent = -frac * 360.0
    color = "#14b8a6" if frac >= 1.0 else "#f59e0b"
    if frac > 0.002:
        canvas.create_arc(
            x0, y0, x1, y1, start=90, extent=extent, style=tk.ARC, outline=color, width=10
        )
    pct = int(round(frac * 100))
    canvas.create_text(
        w // 2, h // 2 - 6, text=f"{pct}%", fill="#f8fafc", font=("Segoe UI", 16, "bold")
    )
    canvas.create_text(
        w // 2, h // 2 + 16, text="study", fill="#94a3b8", font=("Segoe UI", 9)
    )


def _open_window(
    *,
    blocked_app: str,
    productive: int,
    goal: int,
    remaining: int,
    chapter_done: int = 0,
    chapter_target: int = 1,
    day_unlimited: bool = False,
    auto_open_bible: bool = True,
    today_label: str = "",
    gate: dict[str, Any] | None = None,
    user_id: int | None = None,
) -> None:
    global _window

    root = tk.Tk()
    root.title(f"CALT — Today: {today_label}" if today_label else "CALT — Games locked · Read a chapter")
    root.configure(bg="#0f172a")
    root.minsize(420, 420)
    try:
        root.geometry("480x520+80+80")
    except tk.TclError:
        pass

    header = tk.Frame(root, bg="#0f172a", padx=20, pady=16)
    header.pack(fill=tk.X)
    tk.Label(
        header,
        text="Games locked",
        bg="#0f172a",
        fg="#f8fafc",
        font=("Segoe UI", 16, "bold"),
    ).pack(anchor=tk.W)
    tk.Label(
        header,
        text=f"Blocked: {blocked_app or 'game'}",
        bg="#0f172a",
        fg="#f87171",
        font=("Segoe UI", 10),
    ).pack(anchor=tk.W, pady=(4, 0))

    body = tk.Frame(root, bg="#1e293b", padx=20, pady=16)
    body.pack(fill=tk.BOTH, expand=True, padx=16, pady=(0, 8))

    top = tk.Frame(body, bg="#1e293b")
    top.pack(fill=tk.X)
    ring = tk.Canvas(top, width=88, height=88, bg="#1e293b", highlightthickness=0)
    ring.pack(side=tk.LEFT, padx=(0, 16))
    _draw_ring(ring, productive, goal)

    right = tk.Frame(top, bg="#1e293b")
    right.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    tk.Label(
        right,
        text="Unlock for the rest of today",
        bg="#1e293b",
        fg="#f8fafc",
        font=("Segoe UI", 11, "bold"),
    ).pack(anchor=tk.W)
    bible_hint = (
        f"1. Read & tick {today_label} in CALT (/bible)\n2. Hit your study goal\n→ Games unlimited until midnight"
        if today_label
        else "1. Read & tick today’s chapter in CALT (/bible)\n2. Hit your study goal\n→ Games unlimited until midnight"
    )
    tk.Label(
        right,
        text=bible_hint,
        bg="#1e293b",
        fg="#cbd5e1",
        font=("Segoe UI", 9),
        justify=tk.LEFT,
    ).pack(anchor=tk.W, pady=(6, 0))

    stats = tk.Frame(body, bg="#1e293b")
    stats.pack(anchor=tk.W, pady=(16, 0), fill=tk.X)
    rows = [
        ("Study", f"{_fmt_minutes(productive)} / {_fmt_minutes(goal)}"),
        ("Bible today", f"{chapter_done} / {chapter_target} chapter"),
        ("Status", "Unlimited" if day_unlimited else "Locked"),
        ("Study left", _fmt_minutes(remaining) if not day_unlimited else "—"),
    ]
    for label, val in rows:
        cell = tk.Frame(stats, bg="#1e293b")
        cell.pack(side=tk.LEFT, padx=(0, 20))
        tk.Label(cell, text=label, bg="#1e293b", fg="#94a3b8", font=("Segoe UI", 8)).pack(
            anchor=tk.W
        )
        tk.Label(
            cell, text=val, bg="#1e293b", fg="#f8fafc", font=("Segoe UI", 11, "bold")
        ).pack(anchor=tk.W)

    rules_host = tk.Frame(body, bg="#1e293b")
    rules_host.pack(fill=tk.X, pady=(4, 0))

    def _paint_rules(g: dict[str, Any] | None) -> None:
        for child in rules_host.winfo_children():
            child.destroy()
        try:
            from backend.behavior.tracker_rules_gui import (
                build_snapshot_from_gate,
                paint_rules_section,
            )

            snap = build_snapshot_from_gate(g, user_id=user_id, tracker_alive=True)
            paint_rules_section(rules_host, snap, title="Today’s rules")
        except Exception as exc:  # noqa: BLE001
            log.debug("rules section paint failed: %s", exc)

    _paint_rules(gate)

    def _poll_rules() -> None:
        if _window is None:
            return
        try:
            if not root.winfo_exists():
                return
        except tk.TclError:
            return
        fresh = gate
        if user_id:
            try:
                from backend.behavior.distraction_gate import compute_distraction_gate
                from backend.db.base import SessionLocal

                db = SessionLocal()
                try:
                    fresh = compute_distraction_gate(db, int(user_id))
                finally:
                    db.close()
            except Exception as exc:  # noqa: BLE001
                log.debug("rules poll gate: %s", exc)
        _paint_rules(fresh)
        try:
            root.after(15_000, _poll_rules)
        except tk.TclError:
            return

    root.after(15_000, _poll_rules)

    btn_row = tk.Frame(root, bg="#0f172a", padx=16, pady=12)
    btn_row.pack(fill=tk.X)

    def close() -> None:
        global _window
        try:
            root.destroy()
        except tk.TclError:
            pass
        _window = None

    def _msg(title: str, body: str) -> None:
        from tkinter import messagebox

        messagebox.showinfo(title, body, parent=root)

    def _set_status(msg: str) -> None:
        try:
            if msg:
                root.title(msg)
            else:
                root.title(
                    f"CALT — Today: {today_label}"
                    if today_label
                    else "CALT — Games locked · Read a chapter"
                )
        except tk.TclError:
            pass

    def _open_calt(url: str) -> None:
        from backend.behavior.stack_health import open_calt_page

        open_calt_page(
            url,
            on_message=_msg,
            on_status=_set_status,
            parent=root,
            speak=True,
            auto_start=True,
        )

    def open_bible() -> None:
        _open_calt(_target_bible_url())

    def open_productivity() -> None:
        _open_calt(_target_plan_url())

    def start_stack_open_bible() -> None:
        _open_calt(_target_bible_url())

    tk.Button(
        btn_row,
        text="Open Bible reader",
        command=open_bible,
        bg="#0d9488",
        fg="#f0fdfa",
        activebackground="#14b8a6",
        activeforeground="#042f2e",
        relief=tk.FLAT,
        padx=16,
        pady=8,
        cursor="hand2",
        font=("Segoe UI", 10, "bold"),
    ).pack(side=tk.RIGHT, padx=(8, 0))

    tk.Button(
        btn_row,
        text="Start stack & open Bible",
        command=start_stack_open_bible,
        bg="#0f766e",
        fg="#f0fdfa",
        activebackground="#14b8a6",
        relief=tk.FLAT,
        padx=12,
        pady=8,
        cursor="hand2",
        font=("Segoe UI", 9, "bold"),
    ).pack(side=tk.RIGHT, padx=(8, 0))

    tk.Button(
        btn_row,
        text="Open Productivity",
        command=open_productivity,
        bg="#334155",
        fg="#e2e8f0",
        activebackground="#475569",
        relief=tk.FLAT,
        padx=12,
        pady=8,
        cursor="hand2",
        font=("Segoe UI", 9),
    ).pack(side=tk.RIGHT, padx=(8, 0))

    tk.Button(
        btn_row,
        text="Dismiss",
        command=close,
        bg="#334155",
        fg="#e2e8f0",
        activebackground="#475569",
        relief=tk.FLAT,
        padx=12,
        pady=8,
        cursor="hand2",
        font=("Segoe UI", 9),
    ).pack(side=tk.RIGHT)

    root.protocol("WM_DELETE_WINDOW", close)
    _window = root

    # Game-blocked speak (tracker-local TTS — no API/Vite required)
    try:
        from backend.behavior.stack_health import local_jarvis_speak

        local_jarvis_speak("game_blocked", force=False)
    except Exception as exc:  # noqa: BLE001
        log.debug("lock-card jarvis speak skipped: %s", exc)

    if auto_open_bible:
        root.after(200, open_bible)

    root.mainloop()
    _window = None


def show_hard_block_notice(
    *,
    blocked_app: str,
    gate: dict[str, Any] | None,
    force: bool = False,
    user_id: int | None = None,
    auto_open_bible: bool = True,
) -> None:
    """Show compact lock card; primary path is /bible (not PDF). Debounced.

    ``auto_open_bible`` should stay True for game hard-blocks (CTA). Soft-lock /
    rule-break overlays must pass False — auto-open launched Edge + FOCUS storms
    that felt like the study browser closing.
    """
    global _last_show_at, _window
    import time

    now = time.time()
    if not force and (now - _last_show_at) < _MIN_GAP_S:
        return
    g = gate or {}
    productive = int(g.get("productive_minutes") or 0)
    goal = int(g.get("daily_goal_minutes") or 240)
    remaining = int(g.get("remaining_minutes") or max(0, goal - productive))
    cg = g.get("chapter_goal") or {}
    chapter_done = int(cg.get("done") or len(g.get("chapters_completed_today") or []) or 0)
    chapter_target = int(cg.get("target") or 1)
    day_unlimited = bool(g.get("day_unlimited"))
    today_label = ""
    if user_id:
        try:
            from backend.bible import store as bible_store

            tc = bible_store.resolve_today_chapter(int(user_id))
            today_label = str(tc.get("label") or "")
            if tc.get("done"):
                chapter_done = max(chapter_done, 1)
        except Exception as exc:  # noqa: BLE001
            log.debug("today chapter for lock card: %s", exc)

    def runner() -> None:
        global _last_show_at
        with _window_lock:
            if _window is not None:
                try:
                    _window.lift()
                    _window.attributes("-topmost", True)
                    _last_show_at = time.time()
                    return
                except tk.TclError:
                    pass
            _last_show_at = time.time()
            try:
                _open_window(
                    blocked_app=blocked_app,
                    productive=productive,
                    goal=goal,
                    remaining=remaining,
                    chapter_done=chapter_done,
                    chapter_target=chapter_target,
                    day_unlimited=day_unlimited,
                    today_label=today_label,
                    gate=g,
                    user_id=user_id,
                    auto_open_bible=auto_open_bible,
                )
            except Exception as exc:  # noqa: BLE001
                log.warning("hard-block notice failed: %s", exc)

    threading.Thread(target=runner, name="hard-block-gui", daemon=True).start()


_last_ext_redirect_at = 0.0
_EXT_REDIRECT_GAP_S = 12.0


def show_extension_redirect_notice(*, detail: str = "") -> None:
    """Simple Windows dialog when CALT Gate redirects a tab (Edge is not closed)."""
    global _last_ext_redirect_at
    import time

    now = time.time()
    if now - _last_ext_redirect_at < _EXT_REDIRECT_GAP_S:
        return
    _last_ext_redirect_at = now
    label = (detail or "a site").strip()[:120]

    def runner() -> None:
        try:
            import tkinter as tk
            from tkinter import messagebox

            root = tk.Tk()
            root.withdraw()
            try:
                root.attributes("-topmost", True)
            except tk.TclError:
                pass
            messagebox.showinfo(
                "CALT Gate — tab redirected",
                "CALT Gate redirected one Edge tab to the lock page.\n\n"
                "Microsoft Edge was NOT closed.\n\n"
                f"Blocked: {label}\n\n"
                "Log: data/logs/gate_extension.log",
                parent=root,
            )
            root.destroy()
        except Exception as exc:  # noqa: BLE001
            log.warning("extension redirect notice failed: %s", exc)

    threading.Thread(target=runner, name="gate-ext-notice", daemon=True).start()


def show_nsfw_screen_notice(
    *,
    detail: str = "",
    gate: dict[str, Any] | None = None,
    force: bool = False,
    user_id: int | None = None,
) -> None:
    """Soft lock card (rule break / NSFW / unauthorized browser) — never kills.

    Does **not** auto-open Bible/Edge. Soft-lock is overlay + voice only so Edge
    stays up when YouTube Music / Pear or an Edge tab trips the gate.
    """
    label = detail.strip() or "NSFW content on screen"
    show_hard_block_notice(
        blocked_app=f"Soft lock · {label}"[:80],
        gate=gate,
        force=force,
        user_id=user_id,
        auto_open_bible=False,
    )
