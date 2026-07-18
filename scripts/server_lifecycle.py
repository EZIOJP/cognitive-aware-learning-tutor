"""
Smart local server lifecycle for CALT (API :8000, Vite :5173).

Never stops the desktop tracker (backend.behavior.desktop_tracker) —
that is standalone; use scripts\\desktop_tracker\\stop_desktop_tracker.bat.

Designed for run.bat so repeated launches don't hit WinError 10013.
"""
from __future__ import annotations

import argparse
import os
import re
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from dataclasses import dataclass

ROOT = Path(__file__).resolve().parents[1]
API_PORT = 8000
FE_PORT = 5173
API_HEALTH = f"http://127.0.0.1:{API_PORT}/health"
FE_URL = f"http://127.0.0.1:{FE_PORT}/"

# Substrings that mark a process as off-limits for this controller.
PROTECTED_CMDLINE_MARKERS = (
    "desktop_tracker",
    "backend.behavior.desktop_tracker",
    "server_lifecycle.py",  # never kill our own control process
    "stop_desktop_tracker",
)

# Must look like our API / frontend before we kill a port holder.
API_KILL_MARKERS = ("uvicorn", "backend.main")
FE_KILL_MARKERS = ("vite",)


def _py() -> str:
    venv = ROOT / ".venv" / "Scripts" / "python.exe"
    return str(venv) if venv.is_file() else sys.executable


def _creationflags() -> int:
    return getattr(subprocess, "CREATE_NO_WINDOW", 0)


def _norm(s: str) -> str:
    return (s or "").lower().replace("\\", "/")


def _root_hint() -> str:
    return _norm(str(ROOT))


def is_protected_cmdline(cmdline: str | None) -> bool:
    """Desktop tracker and this controller must never be killed."""
    c = _norm(cmdline or "")
    if not c:
        return False
    return any(m in c for m in PROTECTED_CMDLINE_MARKERS)


def is_calt_api_cmdline(cmdline: str | None) -> bool:
    c = _norm(cmdline or "")
    if not c or is_protected_cmdline(c):
        return False
    if not all(m in c for m in API_KILL_MARKERS):
        return False
    # Prefer this repo; still accept explicit uvicorn backend.main (solo PC).
    return True


def is_calt_frontend_cmdline(cmdline: str | None) -> bool:
    c = _norm(cmdline or "")
    if not c or is_protected_cmdline(c):
        return False
    root = _root_hint()
    if "vite" in c and (root in c or "cognitive-aware learning tutor" in c):
        return True
    if "npm" in c and "run" in c and "dev" in c and root in c:
        return True
    return False


def _cmdline_for_pid(pid: int) -> str | None:
    if sys.platform != "win32":
        return None
    script = (
        f"$p = Get-CimInstance Win32_Process -Filter \"ProcessId={pid}\" "
        "-ErrorAction SilentlyContinue; "
        "if ($p) { $p.CommandLine }"
    )
    try:
        out = subprocess.check_output(
            ["powershell", "-NoProfile", "-Command", script],
            text=True,
            errors="replace",
            creationflags=_creationflags(),
        ).strip()
        return out or None
    except (OSError, subprocess.CalledProcessError):
        return None


def _self_and_parents() -> set[int]:
    """Never kill this process or its parents (menu / python)."""
    protected = {os.getpid()}
    try:
        protected.add(os.getppid())
    except AttributeError:
        pass
    return protected


def filter_killable_pids(
    pids: list[int],
    *,
    kind: str,
) -> tuple[list[int], list[tuple[int, str]]]:
    """
    Split PIDs into (killable, skipped_with_reason).
    kind: 'api' | 'frontend' | 'port-api' | 'port-frontend'
    """
    killable: list[int] = []
    skipped: list[tuple[int, str]] = []
    self_ids = _self_and_parents()

    for pid in sorted(set(pids)):
        if pid in self_ids:
            skipped.append((pid, "self/parent — never kill"))
            continue
        cmdline = _cmdline_for_pid(pid)
        if is_protected_cmdline(cmdline):
            skipped.append((pid, "PROTECTED (desktop tracker / control) — left running"))
            continue
        if kind.startswith("port-"):
            # Port holders: only kill if clearly ours; otherwise skip (foreign app).
            role = kind.split("-", 1)[1]
            ok = is_calt_api_cmdline(cmdline) if role == "api" else is_calt_frontend_cmdline(cmdline)
            if not ok:
                preview = (cmdline or "(no cmdline)")[:120]
                skipped.append((pid, f"foreign/unknown on port — not killed: {preview}"))
                continue
        elif kind == "api":
            if not is_calt_api_cmdline(cmdline):
                skipped.append((pid, "not a CALT API process"))
                continue
        elif kind == "frontend":
            if not is_calt_frontend_cmdline(cmdline):
                skipped.append((pid, "not a CALT frontend process"))
                continue
        killable.append(pid)
    return killable, skipped


def _listening_pids(port: int) -> list[int]:
    """PIDs with LISTENING sockets on the exact port (Windows netstat)."""
    try:
        out = subprocess.check_output(
            ["netstat", "-ano"],
            text=True,
            errors="replace",
            creationflags=_creationflags(),
        )
    except (OSError, subprocess.CalledProcessError):
        return []
    pids: set[int] = set()
    port_re = re.compile(rf":{port}(?:\s|$)")
    for line in out.splitlines():
        if "LISTENING" not in line.upper():
            continue
        if not port_re.search(line):
            continue
        parts = line.split()
        if not parts:
            continue
        try:
            pid = int(parts[-1])
        except ValueError:
            continue
        if pid > 0:
            pids.add(pid)
    return sorted(pids)


def _http_ok(url: str, timeout: float = 2.5) -> bool:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            return 200 <= getattr(resp, "status", 200) < 500
    except (urllib.error.URLError, TimeoutError, OSError):
        return False


def _port_free(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            s.bind(("0.0.0.0", port))
            return True
        except OSError:
            return False


def _kill_pids(pids: list[int]) -> None:
    """Kill PIDs. Prefer /F without tree when possible; /T only for confirmed servers."""
    for pid in pids:
        try:
            if sys.platform == "win32":
                # /T kills children — fine for uvicorn/vite workers, not used on protected.
                subprocess.run(
                    ["taskkill", "/PID", str(pid), "/F", "/T"],
                    capture_output=True,
                    text=True,
                    creationflags=_creationflags(),
                )
            else:
                os.kill(pid, 9)
        except OSError:
            pass


def _windows_process_cmdline_pids(needles: list[str]) -> list[int]:
    """Find PIDs whose command line contains all needles (excludes protected in Python)."""
    raw = _windows_process_cmdline_pids_raw(needles)
    out: list[int] = []
    for pid in raw:
        cmd = _cmdline_for_pid(pid)
        if is_protected_cmdline(cmd):
            continue
        out.append(pid)
    return out


def tracker_pids() -> list[int]:
    """Desktop tracker PIDs — always left alone by this controller."""
    return _windows_process_cmdline_pids_raw(["desktop_tracker"])


def _windows_process_cmdline_pids_raw(needles: list[str]) -> list[int]:
    if sys.platform != "win32":
        return []
    ps_needles = [n.replace("'", "''") for n in needles]
    filters = " -and ".join(f"($_.CommandLine -like '*{n}*')" for n in ps_needles)
    # Single f-string so {{ / }} brace escaping is correct for PowerShell scriptblocks.
    script = (
        "Get-CimInstance Win32_Process | "
        f"Where-Object {{ $_.CommandLine -and ({filters}) }} | "
        "Select-Object -ExpandProperty ProcessId"
    )
    try:
        out = subprocess.check_output(
            ["powershell", "-NoProfile", "-Command", script],
            text=True,
            errors="replace",
            creationflags=_creationflags(),
        )
    except (OSError, subprocess.CalledProcessError):
        return []
    return sorted({int(x.strip()) for x in out.splitlines() if x.strip().isdigit()})


def _orphan_calt_pids() -> dict[str, list[int]]:
    """
    Project-related API/frontend processes (never includes desktop tracker).
    """
    api = _windows_process_cmdline_pids(["uvicorn", "backend.main"])
    api = [p for p in api if is_calt_api_cmdline(_cmdline_for_pid(p))]
    fe = _windows_process_cmdline_pids(["vite"])
    fe += _windows_process_cmdline_pids(["npm", "run", "dev"])
    fe = [p for p in fe if is_calt_frontend_cmdline(_cmdline_for_pid(p))]
    for p in _listening_pids(API_PORT):
        if is_calt_api_cmdline(_cmdline_for_pid(p)):
            api.append(p)
    for p in _listening_pids(FE_PORT):
        if is_calt_frontend_cmdline(_cmdline_for_pid(p)):
            fe.append(p)
    return {"api": sorted(set(api)), "frontend": sorted(set(fe))}


def _report_skipped(skipped: list[tuple[int, str]]) -> None:
    for pid, reason in skipped:
        print(f"[servers] SKIP pid {pid}: {reason}")


def _preview_cmdline(pid: int, limit: int = 90) -> str:
    cmd = _cmdline_for_pid(pid) or "(unknown)"
    cmd = " ".join(cmd.split())
    return cmd if len(cmd) <= limit else cmd[: limit - 1] + "…"


@dataclass
class ClosePlan:
    scope: str  # api | frontend | both
    kill_api: list[int]
    kill_frontend: list[int]
    skip: list[tuple[int, str]]
    trackers_before: list[int]
    warnings: list[str]
    api_was_healthy: bool = False
    frontend_was_healthy: bool = False

    @property
    def kill_all(self) -> list[int]:
        return sorted(set(self.kill_api) | set(self.kill_frontend))

    @property
    def empty(self) -> bool:
        return not self.kill_all


def build_close_plan(scope: str) -> ClosePlan:
    """Sanity-check what a close action would do — no kills yet."""
    assert scope in ("api", "frontend", "both")
    trackers = tracker_pids()
    warnings: list[str] = []
    skip: list[tuple[int, str]] = []

    api_listen = _listening_pids(API_PORT)
    fe_listen = _listening_pids(FE_PORT)
    api_healthy = bool(api_listen and _http_ok(API_HEALTH))
    fe_healthy = bool(fe_listen and _http_ok(FE_URL))

    orphans = _orphan_calt_pids()
    api_candidates: list[int] = []
    fe_candidates: list[int] = []

    if scope in ("api", "both"):
        api_candidates = sorted(set(orphans["api"]) | set(api_listen))
    if scope in ("frontend", "both"):
        fe_candidates = sorted(set(orphans["frontend"]) | set(fe_listen))

    api_kill, api_skip = filter_killable_pids(
        api_candidates,
        kind="port-api" if scope != "frontend" else "api",
    )
    # Port holders need port-api filter; orphan-only extras already filtered as api
    api_kill2, api_skip2 = filter_killable_pids(orphans["api"], kind="api")
    if scope in ("api", "both"):
        api_kill = sorted(set(api_kill) | set(api_kill2))
        skip.extend(api_skip + api_skip2)

    fe_kill, fe_skip = filter_killable_pids(fe_candidates, kind="port-frontend")
    fe_kill2, fe_skip2 = filter_killable_pids(orphans["frontend"], kind="frontend")
    if scope in ("frontend", "both"):
        fe_kill = sorted(set(fe_kill) | set(fe_kill2))
        skip.extend(fe_skip + fe_skip2)

    # Deduplicate skip reasons
    seen_skip: set[int] = set()
    uniq_skip: list[tuple[int, str]] = []
    for pid, reason in skip:
        if pid in seen_skip:
            continue
        seen_skip.add(pid)
        uniq_skip.append((pid, reason))

    if scope in ("api", "both") and api_healthy and api_kill:
        warnings.append("API is currently HEALTHY - closing will take down the backend until you start it again.")
    if scope in ("frontend", "both") and fe_healthy and fe_kill:
        warnings.append("Frontend is currently HEALTHY - UI will go offline until you start it again.")
    if trackers:
        warnings.append(f"Desktop tracker stays running (PROTECTED): {trackers}")
    else:
        warnings.append("Desktop tracker is not running (nothing to protect).")

    # Sanity: never include tracker PIDs in kill lists
    tracker_set = set(trackers)
    leaked = [p for p in (api_kill + fe_kill) if p in tracker_set]
    if leaked:
        warnings.append(f"SANITY FAIL blocked tracker PIDs from kill list: {leaked}")
        api_kill = [p for p in api_kill if p not in tracker_set]
        fe_kill = [p for p in fe_kill if p not in tracker_set]

    self_ids = _self_and_parents()
    leaked_self = [p for p in (api_kill + fe_kill) if p in self_ids]
    if leaked_self:
        warnings.append(f"SANITY FAIL blocked self/parent PIDs: {leaked_self}")
        api_kill = [p for p in api_kill if p not in self_ids]
        fe_kill = [p for p in fe_kill if p not in self_ids]

    return ClosePlan(
        scope=scope,
        kill_api=api_kill,
        kill_frontend=fe_kill,
        skip=uniq_skip,
        trackers_before=trackers,
        warnings=warnings,
        api_was_healthy=api_healthy,
        frontend_was_healthy=fe_healthy,
    )


def print_close_plan(plan: ClosePlan) -> None:
    print()
    print("  == Close sanity check ==")
    print(f"  Scope: {plan.scope}")
    print()
    if plan.kill_api:
        print("  WILL CLOSE - API:")
        for pid in plan.kill_api:
            print(f"    * pid {pid}: {_preview_cmdline(pid)}")
    else:
        print("  WILL CLOSE - API: (none)")
    if plan.kill_frontend:
        print("  WILL CLOSE - Frontend:")
        for pid in plan.kill_frontend:
            print(f"    * pid {pid}: {_preview_cmdline(pid)}")
    else:
        print("  WILL CLOSE - Frontend: (none)")
    print()
    print("  WILL KEEP:")
    print(f"    * Desktop tracker: {plan.trackers_before or 'not running'}")
    if plan.skip:
        print("  SKIPPED (not closed):")
        for pid, reason in plan.skip:
            print(f"    * pid {pid}: {reason}")
    if plan.warnings:
        print("  WARNINGS:")
        for w in plan.warnings:
            print(f"    ! {w}")
    print()
    if plan.empty:
        print("  Nothing safe to close.")
    else:
        print(f"  Total processes to close: {len(plan.kill_all)}")
    print("  ========================")
    print()


def confirm_close(plan: ClosePlan) -> bool:
    """Ask before killing. Empty plan → no prompt."""
    print_close_plan(plan)
    if plan.empty:
        return False
    try:
        answer = input("  Proceed with close? [y/N]: ").strip().lower()
    except EOFError:
        print("  No TTY — cancelled (pass non-interactive only via --yes).")
        return False
    return answer in ("y", "yes")


def execute_close_plan(plan: ClosePlan) -> int:
    """Run kills from an already-confirmed plan; verify tracker afterward."""
    if plan.empty:
        print("[servers] Nothing to close")
        return 0

    if plan.kill_api:
        print(f"[servers] Closing API PIDs {plan.kill_api}")
        _kill_pids(plan.kill_api)
    if plan.kill_frontend:
        print(f"[servers] Closing Frontend PIDs {plan.kill_frontend}")
        _kill_pids(plan.kill_frontend)

    time.sleep(0.8)
    if plan.scope in ("api", "both"):
        stop_port(API_PORT, "API", kind="port-api")
    if plan.scope in ("frontend", "both"):
        stop_port(FE_PORT, "Frontend", kind="port-frontend")

    still_trackers = tracker_pids()
    if plan.trackers_before and not still_trackers:
        print("[servers] WARNING: tracker was running and is gone — check desktop tracker")
        return 2
    if plan.trackers_before:
        print(f"[servers] Sanity OK — desktop tracker still running: {still_trackers}")
    else:
        print("[servers] Close finished (no tracker was running)")

    left = _orphan_calt_pids()
    if plan.scope == "api":
        left_show = left["api"]
    elif plan.scope == "frontend":
        left_show = left["frontend"]
    else:
        left_show = left["api"] + left["frontend"]
    if left_show:
        print(f"[servers] WARNING leftovers: {left_show}")
    else:
        print("[servers] Close complete — only API/Frontend targeted; tracker left alone")
    return 0


def close_with_checks(scope: str, *, assume_yes: bool = False) -> int:
    """Build plan → sanity print → confirm → execute."""
    plan = build_close_plan(scope)
    if assume_yes:
        print_close_plan(plan)
        if plan.empty:
            return 0
        return execute_close_plan(plan)
    if not confirm_close(plan):
        print("  Cancelled — nothing closed.")
        return 0
    return execute_close_plan(plan)


def cleanup_unwanted(*, assume_yes: bool = False) -> int:
    """Close unwanted API + Frontend after sanity checks (tracker never touched)."""
    return close_with_checks("both", assume_yes=assume_yes)


def stop_port(port: int, label: str, *, kind: str) -> None:
    """Stop our listeners on port; never kill protected or foreign processes."""
    pids = _listening_pids(port)
    if not pids:
        print(f"[servers] {label} (:{port}) — nothing listening")
        return
    killable, skipped = filter_killable_pids(pids, kind=kind)
    _report_skipped(skipped)
    if not killable:
        print(f"[servers] {label} (:{port}) — no safe CALT PIDs to kill (port may be foreign)")
        return
    print(f"[servers] Stopping {label} (:{port}) PIDs {killable}")
    _kill_pids(killable)
    for _ in range(5):
        time.sleep(0.4)
        leftover = _listening_pids(port)
        still_ours, skip2 = filter_killable_pids(leftover, kind=kind)
        if not still_ours:
            if leftover:
                _report_skipped(skip2)
                print(f"[servers] {label}: our process gone; foreign still on :{port}: {leftover}")
            else:
                print(f"[servers] {label} stopped")
            return
        print(f"[servers] Still on :{port}: {still_ours} — killing again")
        _kill_pids(still_ours)
    leftover = _listening_pids(port)
    if leftover:
        print(f"[servers] WARNING: still listening: {leftover}")


def status() -> int:
    api_pids = _listening_pids(API_PORT)
    fe_pids = _listening_pids(FE_PORT)
    api_health = _http_ok(API_HEALTH) if api_pids else False
    fe_health = _http_ok(FE_URL) if fe_pids else False
    orphans = _orphan_calt_pids()
    trackers = tracker_pids()
    extra_api = [p for p in orphans["api"] if p not in api_pids]
    extra_fe = [p for p in orphans["frontend"] if p not in fe_pids]

    # Flag foreign port holders
    foreign_api, _ = filter_killable_pids(api_pids, kind="port-api")
    foreign_on_api = [p for p in api_pids if p not in foreign_api]
    foreign_fe, _ = filter_killable_pids(fe_pids, kind="port-frontend")
    foreign_on_fe = [p for p in fe_pids if p not in foreign_fe]

    def _line(name: str, port: int, pids: list[int], healthy: bool, url: str) -> None:
        if not pids:
            state = "DOWN"
        elif healthy:
            state = "OK"
        else:
            state = "HUNG"
        pid_s = ",".join(str(p) for p in pids) if pids else "-"
        print(f"  [{state:4}] {name:10} :{port}  pids={pid_s}  {url}")

    print()
    print("  CALT server status")
    print("  ------------------")
    _line("API", API_PORT, api_pids, api_health, API_HEALTH)
    _line("Frontend", FE_PORT, fe_pids, fe_health, FE_URL)
    tr = ",".join(str(p) for p in trackers) if trackers else "-"
    print(f"  [SAFE] Desktop tracker  pids={tr}  (never closed by this menu)")
    if foreign_on_api:
        print(f"  NOTE: foreign process on :{API_PORT}: {foreign_on_api} (won't auto-kill)")
    if foreign_on_fe:
        print(f"  NOTE: foreign process on :{FE_PORT}: {foreign_on_fe} (won't auto-kill)")
    if extra_api or extra_fe:
        print("  Orphans / duplicates (CALT only):")
        if extra_api:
            print(f"    API extras:      {extra_api}")
        if extra_fe:
            print(f"    Frontend extras: {extra_fe}")
        print("  Use option C to close unwanted API/Frontend (tracker stays).")
    print()
    return 0


def restart_api() -> str:
    print("[servers] Restarting API (tracker untouched)…")
    stop_port(API_PORT, "API", kind="port-api")
    orphans = _orphan_calt_pids()["api"]
    killable, skipped = filter_killable_pids(orphans, kind="api")
    _report_skipped(skipped)
    if killable:
        print(f"[servers] Killing orphan API PIDs {killable}")
        _kill_pids(killable)
    time.sleep(0.6)
    return ensure_api(start_if_needed=True)


def restart_frontend() -> str:
    print("[servers] Restarting Frontend (tracker untouched)…")
    stop_port(FE_PORT, "Frontend", kind="port-frontend")
    orphans = _orphan_calt_pids()["frontend"]
    killable, skipped = filter_killable_pids(orphans, kind="frontend")
    _report_skipped(skipped)
    if killable:
        print(f"[servers] Killing orphan Frontend PIDs {killable}")
        _kill_pids(killable)
    time.sleep(0.6)
    return ensure_frontend(start_if_needed=True)


def _spawn_window(title: str, bat: Path) -> None:
    subprocess.Popen(
        ["cmd", "/c", "start", title, "cmd", "/k", "call", str(bat)],
        cwd=str(ROOT),
        shell=False,
    )


def ensure_api(*, start_if_needed: bool = True) -> str:
    pids = _listening_pids(API_PORT)
    if pids and _http_ok(API_HEALTH):
        print(f"[servers] API already healthy (pids {pids}) — reusing")
        return "healthy"

    if pids:
        print(f"[servers] API on :{API_PORT} but not healthy — replacing ours only")
        stop_port(API_PORT, "API", kind="port-api")
        time.sleep(0.5)

    if not start_if_needed:
        return "missing"

    if not _port_free(API_PORT) and _listening_pids(API_PORT):
        if _http_ok(API_HEALTH):
            print("[servers] API became healthy — reusing")
            return "healthy"
        # Foreign holder edge case
        leftover = _listening_pids(API_PORT)
        killable, skipped = filter_killable_pids(leftover, kind="port-api")
        _report_skipped(skipped)
        if not killable:
            print("[servers] Port 8000 busy with foreign process — abort API start")
            return "busy"
        _kill_pids(killable)
        time.sleep(0.5)

    bat = ROOT / "scripts" / "run_backend_no_reload.bat"
    print("[servers] Starting API (no-reload, stable)…")
    _spawn_window("CALT API", bat)
    for _ in range(40):
        time.sleep(0.5)
        if _http_ok(API_HEALTH, timeout=1.5):
            print("[servers] API is up")
            return "started"
    print("[servers] WARNING: API did not pass health check yet (window may still be booting)")
    return "started"


def ensure_frontend(*, start_if_needed: bool = True) -> str:
    pids = _listening_pids(FE_PORT)
    if pids and _http_ok(FE_URL):
        print(f"[servers] Frontend already healthy (pids {pids}) — reusing")
        return "healthy"

    if pids:
        print(f"[servers] Frontend on :{FE_PORT} but not healthy — replacing ours only")
        stop_port(FE_PORT, "Frontend", kind="port-frontend")
        time.sleep(0.5)

    if not start_if_needed:
        return "missing"

    if not _port_free(FE_PORT) and _listening_pids(FE_PORT):
        if _http_ok(FE_URL):
            print("[servers] Frontend became healthy — reusing")
            return "healthy"
        leftover = _listening_pids(FE_PORT)
        killable, skipped = filter_killable_pids(leftover, kind="port-frontend")
        _report_skipped(skipped)
        if not killable:
            print("[servers] Port 5173 busy with foreign process — abort Frontend start")
            return "busy"
        _kill_pids(killable)
        time.sleep(0.5)

    bat = ROOT / "scripts" / "run_frontend.bat"
    print("[servers] Starting Frontend…")
    _spawn_window("CALT Frontend", bat)
    for _ in range(60):
        time.sleep(0.5)
        if _http_ok(FE_URL, timeout=1.5):
            print("[servers] Frontend is up")
            return "started"
    print("[servers] WARNING: Frontend not responding yet (Vite may still be compiling)")
    return "started"


def ensure_api_fast() -> str:
    """Fast click-launch: reuse healthy API, restart hung listener, else start."""
    pids = _listening_pids(API_PORT)
    if pids:
        if _http_ok(API_HEALTH, timeout=0.8):
            print(f"[servers] API healthy (pids {pids}) — reusing")
            return "healthy"
        # Short grace for cold boot, then treat as hung
        for _ in range(4):
            time.sleep(0.5)
            if _http_ok(API_HEALTH, timeout=0.8):
                print(f"[servers] API healthy (pids {pids}) — reusing")
                return "healthy"
        print(f"[servers] API on :{API_PORT} hung/unhealthy (pids {pids}) — restarting")
        stop_port(API_PORT, "API", kind="port-api")
        time.sleep(0.5)
    if not _port_free(API_PORT) and _listening_pids(API_PORT):
        leftover = _listening_pids(API_PORT)
        killable, skipped = filter_killable_pids(leftover, kind="port-api")
        _report_skipped(skipped)
        if not killable:
            print("[servers] API port busy — use control.bat to inspect")
            return "busy"
        _kill_pids(killable)
        time.sleep(0.4)
    print("[servers] Starting API (fast)…")
    _spawn_window("CALT API", ROOT / "scripts" / "run_backend_no_reload.bat")
    for _ in range(24):
        time.sleep(0.5)
        if _http_ok(API_HEALTH, timeout=1.2):
            print("[servers] API is up")
            return "started"
    print("[servers] WARNING: API not healthy yet — check the CALT API window")
    return "starting"


def ensure_frontend_fast() -> str:
    """Fast click-launch: reuse healthy frontend, restart hung listener, else start."""
    pids = _listening_pids(FE_PORT)
    if pids:
        if _http_ok(FE_URL, timeout=0.8):
            print(f"[servers] Frontend healthy (pids {pids}) — reusing")
            return "healthy"
        for _ in range(4):
            time.sleep(0.5)
            if _http_ok(FE_URL, timeout=0.8):
                print(f"[servers] Frontend healthy (pids {pids}) — reusing")
                return "healthy"
        print(f"[servers] Frontend on :{FE_PORT} hung/unhealthy (pids {pids}) — restarting")
        stop_port(FE_PORT, "Frontend", kind="port-frontend")
        time.sleep(0.5)
    if not _port_free(FE_PORT) and _listening_pids(FE_PORT):
        leftover = _listening_pids(FE_PORT)
        killable, skipped = filter_killable_pids(leftover, kind="port-frontend")
        _report_skipped(skipped)
        if not killable:
            print("[servers] Frontend port busy — use control.bat to inspect")
            return "busy"
        _kill_pids(killable)
        time.sleep(0.4)
    print("[servers] Starting Frontend (fast)…")
    _spawn_window("CALT Frontend", ROOT / "scripts" / "run_frontend.bat")
    for _ in range(30):
        time.sleep(0.5)
        if _http_ok(FE_URL, timeout=1.2):
            print("[servers] Frontend is up")
            return "started"
    print("[servers] WARNING: Frontend not ready yet — Vite may still be compiling")
    return "starting"


def ensure_fast() -> int:
    ensure_api_fast()
    ensure_frontend_fast()
    print()
    print("  CALT launch requested")
    print(f"  API:       {API_HEALTH}")
    print(f"  Frontend:  {FE_URL}")
    print("  For status/restart/stop: control.bat")
    return 0


def prepare_api() -> int:
    pids = _listening_pids(API_PORT)
    if pids and _http_ok(API_HEALTH):
        print(f"[servers] API already healthy (pids {pids})")
        return 0
    if pids:
        print(f"[servers] API hung/unhealthy on :{API_PORT} — clearing ours")
        stop_port(API_PORT, "API", kind="port-api")
        time.sleep(0.5)
    leftover = _listening_pids(API_PORT)
    if leftover:
        killable, skipped = filter_killable_pids(leftover, kind="port-api")
        _report_skipped(skipped)
        if leftover and not killable:
            print("[servers] ERROR: port 8000 held by foreign process")
            return 1
        if killable:
            _kill_pids(killable)
            time.sleep(0.4)
        if _listening_pids(API_PORT):
            print("[servers] ERROR: could not free port 8000")
            return 1
    print("[servers] Port 8000 free — start uvicorn")
    return 10


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="CALT local server lifecycle")
    parser.add_argument(
        "command",
        choices=[
            "status",
            "ensure",
            "ensure-fast",
            "ensure-api",
            "ensure-frontend",
            "restart-api",
            "restart-frontend",
            "prepare-api",
            "stop",
            "stop-api",
            "stop-frontend",
            "cleanup",
            "menu",
        ],
    )
    parser.add_argument(
        "--yes",
        "-y",
        action="store_true",
        help="Skip close confirmation (scripts only)",
    )
    args = parser.parse_args(argv)

    if args.command == "status":
        return status()
    if args.command in ("stop", "cleanup"):
        return cleanup_unwanted(assume_yes=args.yes)
    if args.command == "stop-api":
        return close_with_checks("api", assume_yes=args.yes)
    if args.command == "stop-frontend":
        return close_with_checks("frontend", assume_yes=args.yes)
    if args.command == "prepare-api":
        return prepare_api()
    if args.command == "ensure-api":
        ensure_api()
        return 0
    if args.command == "ensure-frontend":
        ensure_frontend()
        return 0
    if args.command == "restart-api":
        # Restart still confirms the close half when interactive
        code = close_with_checks("api", assume_yes=args.yes)
        if code not in (0, 2):
            return code
        ensure_api()
        status()
        return 0
    if args.command == "restart-frontend":
        code = close_with_checks("frontend", assume_yes=args.yes)
        if code not in (0, 2):
            return code
        ensure_frontend()
        status()
        return 0
    if args.command == "ensure":
        ensure_api()
        ensure_frontend()
        status()
        return 0
    if args.command == "ensure-fast":
        return ensure_fast()
    if args.command == "menu":
        return interactive_menu()
    return 1


def interactive_menu() -> int:
    actions = {
        "1": ("Status", lambda: status()),
        "2": ("Start / ensure both (reuse healthy, fix hung)", lambda: (ensure_api(), ensure_frontend(), status())),
        "3": ("Restart API (sanity check → close → start)", lambda: (
            close_with_checks("api"),
            ensure_api(),
            status(),
        )),
        "4": ("Restart Frontend (sanity check → close → start)", lambda: (
            close_with_checks("frontend"),
            ensure_frontend(),
            status(),
        )),
        "5": ("Stop API (sanity check first)", lambda: (close_with_checks("api"), status())),
        "6": ("Stop Frontend (sanity check first)", lambda: (close_with_checks("frontend"), status())),
        "7": ("Stop both API+FE (sanity check first)", lambda: (close_with_checks("both"), status())),
        "8": ("Start API only", lambda: (ensure_api(), status())),
        "9": ("Start Frontend only", lambda: (ensure_frontend(), status())),
        "C": ("Close ALL unwanted (sanity check first)", lambda: (close_with_checks("both"), status())),
        "R": ("Refresh status", lambda: status()),
    }

    while True:
        os.system("cls" if sys.platform == "win32" else "clear")
        print("=" * 54)
        print("  CALT — run / server control")
        print("  API http://localhost:8000   UI http://localhost:5173")
        print("  Close always asks: preview → confirm → then kill")
        print("  Desktop tracker is NEVER stopped here")
        print("=" * 54)
        status()
        print("  Options")
        print("  -------")
        print("  1) Status")
        print("  2) Start / ensure both  (normal 'run' — safe to repeat)")
        print("  3) Restart API          (check → confirm → restart)")
        print("  4) Restart Frontend     (check → confirm → restart)")
        print("  5) Stop API             (check → confirm)")
        print("  6) Stop Frontend        (check → confirm)")
        print("  7) Stop both API+FE     (check → confirm; tracker stays)")
        print("  8) Start API only")
        print("  9) Start Frontend only")
        print("  C) Close ALL unwanted   (check → confirm; never tracker)")
        print("  R) Refresh status")
        print("  0) Exit")
        print()
        choice = input("  Choose: ").strip()
        if choice in ("0", "q", "Q", "exit"):
            print("  Bye.")
            return 0
        key = choice.upper() if choice.upper() in ("R", "C") else choice
        action = actions.get(key)
        if not action:
            print("  Invalid choice.")
            time.sleep(0.8)
            continue
        print()
        print(f"  >> {action[0]}")
        print()
        try:
            action[1]()
        except Exception as exc:  # noqa: BLE001
            print(f"  ERROR: {exc}")
        print()
        input("  Press Enter to continue…")


if __name__ == "__main__":
    raise SystemExit(main())
