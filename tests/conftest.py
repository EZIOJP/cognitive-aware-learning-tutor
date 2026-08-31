"""Test defaults — avoid heavy word seed during API tests."""

import os

import pytest

os.environ.setdefault("SEED_WORDS_ON_STARTUP", "false")
os.environ.setdefault("DEV_MODE", "true")
# Run Huey tasks inline so test-all-profiles jobs complete without a worker.
os.environ.setdefault("HUEY_IMMEDIATE", "1")


_TK_OFFENDERS: list[str] = []

try:  # pragma: no cover - depends on the interpreter having Tk
    import tkinter as _tk
except ImportError:  # pragma: no cover
    _tk = None

if _tk is not None:

    def _no_tk_root(self, *args, **kwargs):
        """Refuse to build a Tk root during tests.

        The desktop tracker opens its lock/NSFW/redirect cards by starting a
        daemon thread that calls ``tk.Tk()`` and then ``mainloop()``. Under
        pytest those threads outlive the test that triggered them, so the Tcl
        interpreter they create is finalized from the wrong thread at
        interpreter exit and kills the run with ``Tcl_AsyncDelete`` *after*
        every test has already reported success. It reproduced roughly once
        every four runs, which is exactly often enough to erode trust in the
        suite.

        Blocking construction here fixes the whole class of failure rather
        than the paths we happen to know about: every caller already wraps the
        window in ``except Exception`` because a display is never guaranteed,
        so refusing looks like "no display" and is handled. Offenders are
        recorded and reported at session end so a new one is visible instead
        of silent.
        """
        import traceback

        _TK_OFFENDERS.append("".join(traceback.format_stack()[:-1]))
        raise RuntimeError("Tk is disabled during tests (tests/conftest.py)")

    _tk.Tk.__init__ = _no_tk_root


def pytest_terminal_summary(terminalreporter, exitstatus, config):
    if not _TK_OFFENDERS:
        return
    terminalreporter.write_sep(
        "-", f"blocked {len(_TK_OFFENDERS)} Tk root(s); stub the caller", yellow=True
    )
    terminalreporter.write_line(_TK_OFFENDERS[0])


def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "integration: optional marker (corpus registry package removed)",
    )


@pytest.fixture(autouse=True)
def _no_desktop_popups(monkeypatch):
    """Keep tracker popups off the developer's desktop during tests.

    The Tk guard above already stops these from leaking an interpreter, but
    without stubbing they still spawn threads and log warnings on every run.
    Stubbing keeps the output clean and the intent obvious.
    """
    for target in (
        "backend.behavior.voice_agent.jarvis_toast.show_jarvis_toast",
        "backend.behavior.tracker_block_gui.show_hard_block_notice",
        "backend.behavior.tracker_block_gui.show_nsfw_screen_notice",
        "backend.behavior.tracker_block_gui.show_extension_redirect_notice",
    ):
        monkeypatch.setattr(target, lambda *a, **k: None)
