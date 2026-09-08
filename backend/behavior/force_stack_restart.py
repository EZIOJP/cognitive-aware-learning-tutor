"""Force-restart CALT API / Vite (and optional rebuild) without the smart skip-if-up path.

Smart ``launch_calt_stack`` only opens run.bat when something is down.
This module always stops listeners on :8000 / :5173, optionally runs
``npm run build``, then starts API + frontend again. Tracker is left alone
unless ``full`` also spawns a tracker restart.
"""

from __future__ import annotations

import logging
import os
import subprocess
import sys
from pathlib import Path
from typing import Literal

from backend.paths import ROOT

log = logging.getLogger("desktop_tracker")

Mode = Literal["stack", "api", "frontend", "full"]


def _python() -> Path:
    venv = ROOT / ".venv" / "Scripts" / "python.exe"
    if venv.is_file():
        return venv
    return Path(sys.executable)


def run_npm_build(*, timeout_s: float = 600.0) -> int:
    """Production Vite build so dist/ matches current source."""
    log.info("Force restart — npm run build")
    try:
        rc = subprocess.call(
            ["npm", "run", "build"],
            cwd=str(ROOT),
            shell=(sys.platform == "win32"),
            timeout=timeout_s,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        log.error("npm run build failed: %s", exc)
        return 1
    if rc != 0:
        log.error("npm run build exit %s", rc)
    return int(rc)


def _load_server_lifecycle():
    """scripts/ is not always a package; load by path like other tools do."""
    import importlib.util
    import sys

    path = ROOT / "scripts" / "server_lifecycle.py"
    name = "calt_server_lifecycle"
    existing = sys.modules.get(name)
    if existing is not None:
        return existing
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load {path}")
    mod = importlib.util.module_from_spec(spec)
    # dataclasses need the module registered before exec_module
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def force_restart_servers(*, mode: Mode = "stack", rebuild: bool = False) -> int:
    """Kill + restart API and/or frontend via server_lifecycle (tracker untouched)."""
    life = _load_server_lifecycle()

    if rebuild:
        brc = run_npm_build()
        if brc != 0:
            log.warning("Continuing force restart after build failure (rc=%s)", brc)

    do_api = mode in ("stack", "api", "full")
    do_fe = mode in ("stack", "frontend", "full")
    rc = 0
    if do_api:
        try:
            life.restart_api()
        except Exception as exc:  # noqa: BLE001
            log.exception("force restart API failed: %s", exc)
            rc = 1
    if do_fe:
        try:
            life.restart_frontend()
        except Exception as exc:  # noqa: BLE001
            log.exception("force restart frontend failed: %s", exc)
            rc = 1
    try:
        life.status()
    except Exception:  # noqa: BLE001
        pass
    return rc


def spawn_force_restart(
    *,
    mode: Mode = "stack",
    rebuild: bool = False,
    then_tracker: bool = False,
) -> bool:
    """Detached worker so the Qt tray UI does not block or die mid-restart."""
    if sys.platform != "win32":
        log.warning("Force stack restart is Windows-only")
        return False
    if mode == "full":
        then_tracker = True
        if not rebuild and "--no-rebuild" not in sys.argv:
            rebuild = True
    py = _python()
    args = [str(py), "-m", "backend.behavior.force_stack_restart", mode]
    if rebuild:
        args.append("--rebuild")
    if then_tracker:
        args.append("--then-tracker")
    creation = getattr(subprocess, "CREATE_NO_WINDOW", 0) | getattr(
        subprocess, "DETACHED_PROCESS", 0
    )
    try:
        # Visible console so you can see build/restart progress
        subprocess.Popen(
            ["cmd", "/c", "start", "CALT force restart", "cmd", "/k"] + args,
            cwd=str(ROOT),
            creationflags=0,
        )
        log.info(
            "Spawned force restart mode=%s rebuild=%s then_tracker=%s",
            mode,
            rebuild,
            then_tracker,
        )
        return True
    except OSError as exc:
        log.warning("Could not spawn force restart: %s", exc)
        try:
            subprocess.Popen(args, cwd=str(ROOT), creationflags=creation, close_fds=True)
            return True
        except OSError as exc2:
            log.warning("Fallback spawn failed: %s", exc2)
            return False


def main_cli(argv: list[str] | None = None) -> int:
    args = list(argv if argv is not None else sys.argv[1:])
    mode: Mode = "stack"
    rebuild = False
    then_tracker = False
    if args and args[0].lower() in ("stack", "api", "frontend", "full"):
        mode = args[0].lower()  # type: ignore[assignment]
        args = args[1:]
    if "--rebuild" in args:
        rebuild = True
    if "--no-rebuild" in args:
        rebuild = False
    if "--then-tracker" in args:
        then_tracker = True
    if mode == "full":
        then_tracker = True
        if "--no-rebuild" not in args:
            rebuild = True

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [force_stack_restart] %(message)s",
        datefmt="%H:%M:%S",
        force=True,
    )
    try:
        from backend.behavior.tracker_storage import setup_file_logging

        setup_file_logging()
    except Exception:  # noqa: BLE001
        pass

    rc = force_restart_servers(mode=mode, rebuild=rebuild)

    if then_tracker:
        os.environ["CALT_TRACKER_SKIP_STOP_PIN"] = "1"
        try:
            from backend.behavior.tracker_restart import run_restart

            trc = run_restart()
            if trc != 0:
                rc = trc
        except Exception as exc:  # noqa: BLE001
            log.exception("then-tracker restart failed: %s", exc)
            rc = 1
    return rc


if __name__ == "__main__":
    raise SystemExit(main_cli())
