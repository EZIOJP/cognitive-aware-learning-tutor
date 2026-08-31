"""Authentic comms incidents — why Edge closed / rules idle, and how to fix.

JSONL: data/logs/comms_incidents.jsonl
Last N: data/behavior/comms_incidents.json
"""

from __future__ import annotations

import json
import logging
import threading
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from backend.paths import ROOT

log = logging.getLogger("desktop_tracker.comms")
_JSONL = ROOT / "data" / "logs" / "comms_incidents.jsonl"
_LAST_PATH = ROOT / "data" / "behavior" / "comms_incidents.json"
_lock = threading.Lock()
_KEEP = 40

# Case id → (why, how to solve). Keys match classify_extension()["cases"].
PLAYBOOK: dict[str, tuple[str, str]] = {
    "never_seen": (
        "No real extension heartbeat yet (dashboard polls do not count).",
        "In edge://extensions, Load unpacked SelfTracker and CALT Gate. Browse once so they poll the API.",
    ),
    "fresh_poll": (
        "Extensions are polling — this is healthy.",
        "No action. If a site still loads, check CALT Gate is enabled and not in circuit-breaker pause.",
    ),
    "mv3_asleep": (
        "Edge put the extension service worker to sleep. Not uninstalled.",
        "Click any tab in Edge to wake it. Do not Reload unless it stays silent >3 minutes with API up.",
    ),
    "api_down_silent": (
        "API is down, so extensions cannot heartbeat. Looks dead, is not.",
        "Run scripts\\update_and_restart.bat api  — do not close Edge.",
    ),
    "startup_grace": (
        "API or tracker just came back. Waiting for extensions to poll again.",
        "Wait ~90 seconds. If still silent, Reload both extensions in edge://extensions.",
    ),
    "both_silent_api_up": (
        "SelfTracker and CALT Gate both stopped polling while the API is up.",
        "edge://extensions → enable + Reload both. If they were removed, Load unpacked from selftracker-extension and calt-gate-extension.",
    ),
    "partial_gate_dead": (
        "CALT Gate is silent but SelfTracker is alive — blocking may be weak.",
        "Reload CALT Gate only. Leave Edge open.",
    ),
    "partial_selftracker_dead": (
        "SelfTracker is silent but CALT Gate is alive — tracking may be weak.",
        "Reload SelfTracker only. Leave Edge open.",
    ),
    "circuit_breaker": (
        "Too many tab redirects; the gate paused itself so Edge would not crash.",
        "Wait ~3 minutes or toggle CALT Gate off/on. Avoid opening many blocked tabs at once.",
    ),
    "circuit_expired": (
        "An old circuit-breaker pause expired. Redirects should work again.",
        "If a blocked site still opens, Reload CALT Gate.",
    ),
    "mode_mismatch": (
        "API day-mode and the extension cache disagree, so rules lag one poll.",
        "Wait one gate poll (~12s) or click a tab. If it sticks, Reload CALT Gate.",
    ),
    "free_mode_hold": (
        "Free browsing is on — Edge is allowed even if extensions look dead.",
        "Arm study mode / hard-block when you want the gate again. Tray → Today's rules.",
    ),
    "two_strike_pending": (
        "First dead observation. Edge is still open until a second confirm.",
        "If you just reloaded extensions, ignore this. If they are really off, the next poll may close Edge.",
    ),
    "edge_closed": (
        "Tracker closed Microsoft Edge because extensions were confirmed absent (two-strike).",
        "Reload SelfTracker + CALT Gate, then reopen Edge yourself. Do not use a second browser.",
    ),
    "edge_quit": (
        "Edge quit or crashed on its own — the tracker did not close it. "
        "Gate service worker was likely Inactive; SelfTracker may show Errors.",
        "Reopen Edge yourself. edge://extensions → click Errors on SelfTracker, then Reload both. "
        "Do not close Edge. Do not load a second browser.",
    ),
    "watch_stale": (
        "Watch health dump is older than 36 hours.",
        "Phone Zepp → CALT Sync → Send. Use PC LAN IP, not localhost.",
    ),
}

_DEFAULT_FIX = (
    "Reload SelfTracker and CALT Gate in edge://extensions. "
    "Restart API if health is down: scripts\\update_and_restart.bat api."
)


def playbook_for(cases: list[str] | None, *, kind: str = "") -> tuple[str, str]:
    """Return (why, how_to_fix) from the strongest matching case."""
    if kind == "edge_closed":
        why, fix = PLAYBOOK["edge_closed"]
        extra = [PLAYBOOK[c][0] for c in (cases or []) if c in PLAYBOOK and c != "edge_closed"]
        if extra:
            why = why + " Detail: " + extra[0]
        return why, fix
    if kind == "edge_quit":
        why, fix = PLAYBOOK["edge_quit"]
        extra = [
            PLAYBOOK[c][0]
            for c in (cases or [])
            if c in PLAYBOOK and c not in ("edge_quit", "edge_closed")
        ]
        if extra:
            why = why + " Detail: " + extra[0]
        return why, fix
    for c in cases or []:
        if c in PLAYBOOK:
            return PLAYBOOK[c]
    if kind:
        return (f"Comms event: {kind}", _DEFAULT_FIX)
    return ("No comms issue recorded.", "Nothing to fix.")


def authentic_facts(snap: dict[str, Any] | None) -> dict[str, Any]:
    """Numbers the tracker actually used — not guesses."""
    snap = snap or {}
    ext = dict(snap.get("extension") or {})
    return {
        "api_up": bool(snap.get("api_up")),
        "web_up": bool(snap.get("web_up")),
        "startup_grace": bool(snap.get("startup_grace")),
        "extension_status": ext.get("status"),
        "selftracker_status": ext.get("selftracker_status"),
        "calt_gate_status": ext.get("calt_gate_status"),
        "selftracker_age_s": ext.get("selftracker_age_s"),
        "calt_gate_age_s": ext.get("calt_gate_age_s"),
        "age_s": ext.get("age_s"),
        "cases": list(ext.get("cases") or []),
        "false_positives": list(ext.get("false_positives") or []),
        "false_negatives": list(ext.get("false_negatives") or []),
        "dead_strikes": snap.get("dead_strikes"),
        "last_edge_close_at": snap.get("last_edge_close_at"),
        "why_rules_idle": list(snap.get("why_rules_idle") or [])[:4],
    }


def build_incident(
    *,
    kind: str,
    snap: dict[str, Any] | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    facts = authentic_facts(snap)
    cases = list(facts.get("cases") or [])
    if kind == "edge_closed" and "edge_closed" not in cases:
        cases = ["edge_closed", *cases]
    if kind == "edge_quit" and "edge_quit" not in cases:
        cases = ["edge_quit", *cases]
    why, fix = playbook_for(cases, kind=kind)
    row: dict[str, Any] = {
        "ts": datetime.now(UTC).isoformat(),
        "kind": kind,
        "why": why,
        "how_to_fix": fix,
        "facts": facts,
    }
    if extra:
        row["extra"] = extra
    return row


def append_incident(row: dict[str, Any]) -> Path:
    _JSONL.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(row, ensure_ascii=False, default=str)
    with _lock:
        with _JSONL.open("a", encoding="utf-8") as fh:
            fh.write(line + "\n")
        last: list[dict[str, Any]] = []
        if _LAST_PATH.is_file():
            try:
                raw = json.loads(_LAST_PATH.read_text(encoding="utf-8"))
                if isinstance(raw, list):
                    last = [x for x in raw if isinstance(x, dict)]
            except Exception:
                last = []
        last.append(row)
        last = last[-_KEEP:]
        _LAST_PATH.parent.mkdir(parents=True, exist_ok=True)
        _LAST_PATH.write_text(json.dumps(last, indent=2), encoding="utf-8")
    log.warning("comms %s — %s | fix: %s", row.get("kind"), row.get("why"), row.get("how_to_fix"))
    return _JSONL


def recent_incidents(*, limit: int = 15) -> list[dict[str, Any]]:
    try:
        if _LAST_PATH.is_file():
            raw = json.loads(_LAST_PATH.read_text(encoding="utf-8"))
            if isinstance(raw, list):
                rows = [x for x in raw if isinstance(x, dict)]
                return rows[-max(1, limit) :]
    except Exception:
        pass
    return []


def last_incident() -> dict[str, Any] | None:
    rows = recent_incidents(limit=1)
    return rows[-1] if rows else None


def compact_incident(row: dict[str, Any] | None) -> dict[str, Any] | None:
    if not row:
        return None
    facts = dict(row.get("facts") or {})
    return {
        "ts": row.get("ts"),
        "kind": row.get("kind"),
        "why": row.get("why"),
        "how_to_fix": row.get("how_to_fix"),
        "facts": {
            "api_up": facts.get("api_up"),
            "web_up": facts.get("web_up"),
            "extension_status": facts.get("extension_status"),
            "selftracker_status": facts.get("selftracker_status"),
            "calt_gate_status": facts.get("calt_gate_status"),
            "selftracker_age_s": facts.get("selftracker_age_s"),
            "calt_gate_age_s": facts.get("calt_gate_age_s"),
            "cases": list(facts.get("cases") or [])[:8],
            "dead_strikes": facts.get("dead_strikes"),
        },
        "extra": dict(row.get("extra") or {}),
    }


def live_issue(cases: list[str] | None) -> dict[str, Any]:
    why, fix = playbook_for(cases or [])
    return {"why": why, "how_to_fix": fix, "cases": list(cases or [])}


def format_comms_lines(snap: dict[str, Any] | None) -> list[str]:
    """Authentic tray / rules-panel lines (live numbers, not guesses)."""
    snap = snap or {}
    ext = dict(snap.get("extension") or {})
    st_age = ext.get("selftracker_age_s")
    gt_age = ext.get("calt_gate_age_s")

    def _age(v: Any) -> str:
        if v is None:
            return "never"
        try:
            return f"{int(float(v))}s"
        except (TypeError, ValueError):
            return "?"

    lines = [
        (
            f"Ext {ext.get('status') or '?'} · "
            f"ST {ext.get('selftracker_status') or '—'} ({_age(st_age)}) · "
            f"Gate {ext.get('calt_gate_status') or '—'} ({_age(gt_age)})"
        ),
        (
            f"API {'up' if snap.get('api_up') else 'down'} · "
            f"Web {'up' if snap.get('web_up') else 'down'}"
            + (" · startup grace" if snap.get("startup_grace") else "")
        ),
    ]
    issue = dict(snap.get("current_issue") or {})
    if issue.get("why"):
        lines.append(f"Why: {issue['why']}")
    if issue.get("how_to_fix"):
        lines.append(f"Fix: {issue['how_to_fix']}")
    last = dict(snap.get("last_incident") or {})
    if last.get("kind") in ("edge_closed", "edge_quit") and last.get("why"):
        lines.append(f"Last Edge close: {last['why']}")
        if last.get("how_to_fix"):
            lines.append(f"Then: {last['how_to_fix']}")
    return lines


def log_path() -> Path:
    return _JSONL


def maybe_announce_edge_gone(*, running: bool) -> dict[str, Any] | None:
    """If Edge just disappeared (crash/quit, not tracker kill), log + speak + Tk."""
    from backend.behavior.comms_health import observe_edge_presence, snapshot

    if not observe_edge_presence(running):
        return None
    snap = snapshot()
    row = build_incident(
        kind="edge_quit",
        snap=snap,
        extra={"source": "process_watch", "running": False},
    )
    append_incident(row)
    announce_edge_event(row)
    return row


def announce_edge_event(row: dict[str, Any]) -> None:
    """Speak + on-screen why. Used for tracker kills and unexpected quits."""
    why = str(row.get("why") or "Edge is gone.")
    fix = str(row.get("how_to_fix") or _DEFAULT_FIX)
    kind = str(row.get("kind") or "")
    lead = (
        "Microsoft Edge quit or crashed. The tracker did not close it. "
        if kind == "edge_quit"
        else "Closing Microsoft Edge. Extensions stopped polling while the API was up. "
    )
    speak = lead + (fix.split(".")[0] if fix else "Reload both extensions") + "."
    title = "CALT — Edge quit / crashed" if kind == "edge_quit" else "CALT — Edge closed"
    try:
        from backend.behavior.gate_alerts import speak_alert

        speak_alert(speak[:280], force=True)
    except Exception as exc:  # noqa: BLE001
        log.warning("edge notice speak failed: %s", exc)
    try:
        _show_notice(why, fix, title=title)
    except Exception as exc:  # noqa: BLE001
        log.warning("edge notice Tk failed: %s", exc)
        _fallback_notice(title, why, fix)


def announce_edge_close(row: dict[str, Any]) -> None:
    """Speak + on-screen why, every time Edge is actually closed by the tracker."""
    announce_edge_event(row)


_notice_lock = threading.Lock()
_notice_window: Any = None


def _show_notice(why: str, fix: str, *, title: str = "CALT — Edge closed") -> None:
    """Tk notice on a dedicated thread (same pattern as Today's rules)."""
    global _notice_window
    shown = threading.Event()

    with _notice_lock:
        win = _notice_window
        if win is not None:
            try:
                if win.winfo_exists():
                    win.after(0, win.deiconify)
                    win.after(0, win.lift)
                    win.after(0, win.focus_force)
                    return
            except Exception:
                _notice_window = None

    def _run() -> None:
        global _notice_window
        try:
            import tkinter as tk

            root = tk.Tk()
            _notice_window = root
            root.title(title)
            root.configure(bg="#0f172a")
            root.attributes("-topmost", True)
            root.resizable(False, False)
            tk.Label(
                root,
                text="Why Edge closed",
                bg="#0f172a",
                fg="#f8fafc",
                font=("Segoe UI", 12, "bold"),
            ).pack(anchor="w", padx=16, pady=(14, 4))
            tk.Label(
                root,
                text=why,
                bg="#0f172a",
                fg="#fbbf24",
                wraplength=420,
                justify="left",
                font=("Segoe UI", 10),
            ).pack(anchor="w", padx=16, pady=4)
            tk.Label(
                root,
                text="How to fix",
                bg="#0f172a",
                fg="#94a3b8",
                font=("Segoe UI", 9, "bold"),
            ).pack(anchor="w", padx=16, pady=(8, 2))
            tk.Label(
                root,
                text=fix,
                bg="#0f172a",
                fg="#e2e8f0",
                wraplength=420,
                justify="left",
                font=("Segoe UI", 10),
            ).pack(anchor="w", padx=16, pady=(0, 8))
            tk.Button(
                root,
                text="OK — I will Reload extensions",
                command=root.destroy,
                bg="#1a9b8e",
                fg="#fff",
                relief="flat",
                padx=12,
                pady=6,
            ).pack(pady=(4, 14))
            shown.set()
            root.mainloop()
        except Exception as exc:  # noqa: BLE001
            log.warning("edge notice Tk failed: %s", exc)
            if not shown.is_set():
                _fallback_notice(title, why, fix)
        finally:
            _notice_window = None

    threading.Thread(target=_run, daemon=True, name="edge-gone-notice").start()

    def _watch() -> None:
        if not shown.wait(2.5):
            log.warning("edge notice Tk did not map; using MessageBox fallback")
            _fallback_notice(title, why, fix)

    threading.Thread(target=_watch, daemon=True, name="edge-notice-watch").start()


def _fallback_notice(title: str, why: str, fix: str) -> None:
    """Win32 MessageBox if Tk cannot map a window (pystray / no display)."""
    try:
        import ctypes

        text = f"{why}\n\nHow to fix:\n{fix}"
        # MB_ICONWARNING | MB_SYSTEMMODAL | MB_SETFOREGROUND | MB_TOPMOST
        ctypes.windll.user32.MessageBoxW(0, text[:1024], title[:120], 0x30 | 0x1000 | 0x10000 | 0x40000)
    except Exception as exc:  # noqa: BLE001
        log.warning("edge notice MessageBox failed: %s", exc)


def open_incident_log() -> None:
    import os
    import sys

    _JSONL.parent.mkdir(parents=True, exist_ok=True)
    if not _JSONL.exists():
        _JSONL.write_text("", encoding="utf-8")
    if sys.platform == "win32":
        os.startfile(str(_JSONL))  # noqa: S606
