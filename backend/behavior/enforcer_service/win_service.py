"""Optional pywin32 Windows Service wrapper for CALT Enforcer.

Install (admin):
  python -m backend.behavior.enforcer_service.win_service install
  python -m backend.behavior.enforcer_service.win_service start

Without pywin32, use Task Scheduler:
  scripts\\desktop_tracker\\install_enforcer_service.ps1 -Start
"""

from __future__ import annotations

import sys


def _missing_pywin32() -> int:
    print(
        "pywin32 not installed — cannot register an SCM Windows Service.\n"
        "  pip install pywin32\n"
        "Or use Task Scheduler (no admin):\n"
        "  powershell -ExecutionPolicy Bypass -File "
        "scripts\\desktop_tracker\\install_enforcer_service.ps1 -Start",
        file=sys.stderr,
    )
    return 2


try:
    import servicemanager
    import win32event
    import win32service
    import win32serviceutil
except ImportError:
    servicemanager = None  # type: ignore
    win32event = None  # type: ignore
    win32service = None  # type: ignore
    win32serviceutil = None  # type: ignore


if win32serviceutil is not None:

    class CaltEnforcerService(win32serviceutil.ServiceFramework):
        _svc_name_ = "CALTEnforcer"
        _svc_display_name_ = "CALT Desktop Enforcer"
        _svc_description_ = (
            "Hard-block process kills for CALT Desktop Focus "
            "(survives closing the Desktop UI)."
        )

        def __init__(self, args):
            win32serviceutil.ServiceFramework.__init__(self, args)
            self._stop = win32event.CreateEvent(None, 0, 0, None)
            self._thread = None

        def SvcStop(self):
            self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
            win32event.SetEvent(self._stop)
            try:
                from backend.behavior.enforcer_ownership import release_ownership

                release_ownership()
            except Exception:
                pass

        def SvcDoRun(self):
            import threading

            from backend.behavior.enforcer_service.service import (
                _configure_logging,
                run_loop,
            )

            _configure_logging()
            stop_event = threading.Event()

            def _wait_scm():
                win32event.WaitForSingleObject(self._stop, win32event.INFINITE)
                stop_event.set()

            waiter = threading.Thread(target=_wait_scm, daemon=True)
            waiter.start()
            servicemanager.LogInfoMsg("CALT Enforcer starting")
            try:
                run_loop(stop_event=stop_event)
            finally:
                servicemanager.LogInfoMsg("CALT Enforcer stopped")

    def main() -> int:
        win32serviceutil.HandleCommandLine(CaltEnforcerService)
        return 0

else:

    def main() -> int:
        return _missing_pywin32()


if __name__ == "__main__":
    raise SystemExit(main())
