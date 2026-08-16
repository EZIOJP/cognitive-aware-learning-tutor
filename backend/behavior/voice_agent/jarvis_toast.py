"""Topmost Jarvis toast while TTS plays (tracker-local, no web required).

Draggable · word typewriter. Keeps a Tk event pump running while visible so
drag works (a single update() is not enough).
"""

from __future__ import annotations

import logging
import threading
import time
import tkinter as tk

log = logging.getLogger("desktop_tracker.jarvis_toast")

_lock = threading.Lock()
_win: tk.Toplevel | None = None
_root: tk.Tk | None = None
_hide_at: float = 0.0
_type_after: str | None = None
_drag: dict[str, float | bool] = {"active": False, "ox": 0.0, "oy": 0.0}
_pump_thread: threading.Thread | None = None
_last_text: str = ""


def show_jarvis_toast(text: str, *, ms: int = 8000) -> None:
    """Show a topmost caption; safe to call from any thread."""
    text = (text or "").strip()
    if not text:
        return
    text = text[:280]

    def _run() -> None:
        global _win, _root, _hide_at, _type_after, _pump_thread, _last_text
        try:
            with _lock:
                # Same line still on screen — extend hide; do not recreate/loop typewriter.
                if (
                    _win is not None
                    and _last_text == text
                    and time.time() < _hide_at
                ):
                    hide_ms = max(int(ms), 2000 + len(text.split()) * 280)
                    _hide_at = time.time() + hide_ms / 1000.0
                    return
                _last_text = text
                if _root is None:
                    _root = tk.Tk()
                    _root.withdraw()
                    try:
                        _root.attributes("-topmost", True)
                    except tk.TclError:
                        pass
                if _win is not None:
                    try:
                        if _type_after is not None:
                            _win.after_cancel(_type_after)
                    except Exception:
                        pass
                    try:
                        _win.destroy()
                    except tk.TclError:
                        pass
                    _win = None

                win = tk.Toplevel(_root)
                _win = win
                win.overrideredirect(True)
                win.configure(bg="#0f172a")
                try:
                    win.attributes("-topmost", True)
                    win.attributes("-alpha", 0.94)
                except tk.TclError:
                    pass

                grip = tk.Label(
                    win,
                    text="⠿ Jarvis · drag me",
                    bg="#0f172a",
                    fg="#94a3b8",
                    font=("Segoe UI", 8),
                    anchor="w",
                    padx=14,
                    pady=6,
                    cursor="fleur",
                )
                grip.pack(fill=tk.X)
                lbl = tk.Label(
                    win,
                    text="Jarvis:",
                    bg="#0f172a",
                    fg="#e2e8f0",
                    font=("Segoe UI", 10),
                    wraplength=420,
                    justify=tk.LEFT,
                    padx=14,
                    pady=(0, 12),
                    cursor="fleur",
                )
                lbl.pack()

                def _start_drag(event: tk.Event) -> None:  # type: ignore[name-defined]
                    _drag["active"] = True
                    _drag["ox"] = float(event.x_root) - float(win.winfo_x())
                    _drag["oy"] = float(event.y_root) - float(win.winfo_y())

                def _on_drag(event: tk.Event) -> None:  # type: ignore[name-defined]
                    if not _drag.get("active"):
                        return
                    x = int(float(event.x_root) - float(_drag["ox"]))
                    y = int(float(event.y_root) - float(_drag["oy"]))
                    win.geometry(f"+{max(0, x)}+{max(0, y)}")

                def _end_drag(_event: tk.Event | None = None) -> None:  # type: ignore[name-defined]
                    _drag["active"] = False

                for w in (win, grip, lbl):
                    w.bind("<ButtonPress-1>", _start_drag)
                    w.bind("<B1-Motion>", _on_drag)
                    w.bind("<ButtonRelease-1>", _end_drag)

                win.update_idletasks()
                sw = win.winfo_screenwidth()
                req_w = win.winfo_reqwidth()
                win.geometry(f"+{max(8, sw - req_w - 24)}+48")

                words = text.split()
                state = {"i": 0}

                def _tick() -> None:
                    global _type_after
                    i = int(state["i"])
                    if _win is None or i >= len(words):
                        _type_after = None
                        return
                    lbl.configure(text="Jarvis: " + " ".join(words[: i + 1]))
                    state["i"] = i + 1
                    try:
                        _type_after = win.after(280, _tick)
                    except tk.TclError:
                        _type_after = None

                if words:
                    _tick()
                else:
                    lbl.configure(text="Jarvis:")

                hide_ms = max(int(ms), 2000 + len(words) * 280)
                _hide_at = time.time() + hide_ms / 1000.0

            # Pump Tk events so drag/typewriter work (must not hold _lock).
            def _pump() -> None:
                global _win, _type_after, _hide_at
                while True:
                    with _lock:
                        live = _win is not None and _root is not None
                        done = time.time() >= _hide_at
                    if not live:
                        return
                    if done:
                        with _lock:
                            if _type_after is not None and _win is not None:
                                try:
                                    _win.after_cancel(_type_after)
                                except Exception:
                                    pass
                                _type_after = None
                            if _win is not None:
                                try:
                                    _win.destroy()
                                except tk.TclError:
                                    pass
                                _win = None
                        return
                    try:
                        if _root is not None:
                            _root.update()
                    except tk.TclError:
                        return
                    time.sleep(0.02)

            if _pump_thread is None or not _pump_thread.is_alive():
                _pump_thread = threading.Thread(target=_pump, daemon=True, name="jarvis-toast-pump")
                _pump_thread.start()
        except Exception as exc:  # noqa: BLE001
            log.debug("jarvis toast failed: %s", exc)

    try:
        threading.Thread(target=_run, daemon=True, name="jarvis-toast").start()
    except Exception as exc:  # noqa: BLE001
        log.debug("jarvis toast thread failed: %s", exc)
