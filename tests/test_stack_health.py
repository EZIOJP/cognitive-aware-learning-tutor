"""Stack health probes for desktop tracker (API :8000 + Vite :5173)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from backend.behavior import stack_health as sh


def test_default_urls():
    assert "127.0.0.1:8000" in sh.api_health_url()
    assert sh.api_health_url().endswith("/health")
    assert "127.0.0.1:5173" in sh.frontend_url()


def test_probe_url_ok_on_200(monkeypatch):
    resp = MagicMock()
    resp.status = 200
    resp.__enter__ = lambda s: s
    resp.__exit__ = MagicMock(return_value=False)

    with patch("urllib.request.urlopen", return_value=resp) as mock_open:
        assert sh.probe_url("http://127.0.0.1:8000/health") is True
        mock_open.assert_called_once()
        req = mock_open.call_args[0][0]
        assert req.get_method() == "GET"
        assert "8000" in req.full_url


def test_probe_url_false_on_error():
    with patch("urllib.request.urlopen", side_effect=OSError("down")):
        assert sh.probe_url("http://127.0.0.1:8000/health") is False


def test_probe_url_false_on_5xx():
    resp = MagicMock()
    resp.status = 503
    resp.__enter__ = lambda s: s
    resp.__exit__ = MagicMock(return_value=False)
    with patch("urllib.request.urlopen", return_value=resp):
        assert sh.probe_url("http://127.0.0.1:5173/") is False


def test_probe_stack_independent_endpoints():
    def fake_probe(url: str, **_kw) -> bool:
        if "/health" in url:
            return False
        return True

    with patch.object(sh, "probe_url", side_effect=fake_probe):
        snap = sh.probe_stack()
    assert snap.api_up is False
    assert snap.web_up is True
    assert "API: down" in snap.status_line()
    assert "Web: up" in snap.status_line()


def test_cached_status_respects_interval(monkeypatch):
    sh.reset_cache_for_tests()
    calls = {"n": 0}

    def fake_probe(**_kw):
        calls["n"] += 1
        return sh.StackHealth(api_up=True, web_up=False)

    monkeypatch.setattr(sh, "probe_stack", fake_probe)
    monkeypatch.setattr(sh, "PROBE_INTERVAL_S", 30.0)

    t = {"now": 1000.0}
    monkeypatch.setattr(sh.time, "monotonic", lambda: t["now"])

    a = sh.get_stack_health(force=True)
    b = sh.get_stack_health()
    assert calls["n"] == 1
    assert a.api_up is True and b.web_up is False

    t["now"] = 1010.0  # still within interval
    sh.get_stack_health()
    assert calls["n"] == 1

    t["now"] = 1031.0
    sh.get_stack_health()
    assert calls["n"] == 2


def test_transition_to_down_rate_limited(monkeypatch):
    sh.reset_cache_for_tests()
    monkeypatch.setattr(sh, "JARVIS_DOWN_COOLDOWN_S", 60.0)
    t = {"now": 5000.0}
    monkeypatch.setattr(sh.time, "monotonic", lambda: t["now"])

    # Seed: both up
    sh._apply_probe_result(sh.StackHealth(api_up=True, web_up=True), now=t["now"])
    assert sh.maybe_jarvis_stack_down_line() is None

    # API goes down
    t["now"] = 5001.0
    sh._apply_probe_result(sh.StackHealth(api_up=False, web_up=True), now=t["now"])
    line = sh.maybe_jarvis_stack_down_line()
    assert line
    assert "API" in line or "api" in line.lower() or "stack" in line.lower() or "backend" in line.lower()

    # Immediate re-fire blocked
    assert sh.maybe_jarvis_stack_down_line() is None

    # Web also drops later — still in cooldown (pending kept for later)
    t["now"] = 5020.0
    sh._apply_probe_result(sh.StackHealth(api_up=False, web_up=False), now=t["now"])
    assert sh.maybe_jarvis_stack_down_line() is None

    # After cooldown, deferred web-down announces
    t["now"] = 5070.0
    deferred = sh.maybe_jarvis_stack_down_line()
    assert deferred
    assert "Web" in deferred or "frontend" in deferred.lower() or "UI" in deferred or "Vite" in deferred

    # Recover then drop web again — needs cooldown again
    t["now"] = 5071.0
    sh._apply_probe_result(sh.StackHealth(api_up=True, web_up=True), now=t["now"])
    t["now"] = 5072.0
    sh._apply_probe_result(sh.StackHealth(api_up=True, web_up=False), now=t["now"])
    assert sh.maybe_jarvis_stack_down_line() is None  # still in cooldown from deferred
    t["now"] = 5140.0
    line2 = sh.maybe_jarvis_stack_down_line()
    assert line2
    assert "Web" in line2 or "frontend" in line2.lower() or "UI" in line2 or "Vite" in line2


def test_hub_up_does_not_imply_api_up():
    """Documented contract: hub :8765 ≠ FastAPI :8000."""
    with patch.object(
        sh,
        "probe_url",
        side_effect=lambda url, **_k: "8765" in url,
    ):
        # probe_stack only hits API health + FE — never hub
        snap = sh.probe_stack()
    assert snap.api_up is False
    assert snap.web_up is False


def test_open_guard_blocks_when_web_down():
    msgs: list[tuple[str, str]] = []
    health = sh.StackHealth(api_up=False, web_up=False)
    with patch("webbrowser.open") as opened:
        ok = sh.open_app_page_guard(
            "http://127.0.0.1:5173/bible",
            health=health,
            on_message=lambda t, b: msgs.append((t, b)),
            on_offer_start=lambda _spec: False,  # Cancel
            speak=False,
        )
    assert ok is False
    assert opened.call_count == 0


def test_open_guard_starts_then_opens_when_user_accepts(monkeypatch):
    sh.reset_cache_for_tests()
    health = sh.StackHealth(api_up=False, web_up=False)
    calls: dict[str, int] = {"start": 0, "open": 0}

    monkeypatch.setattr(
        sh,
        "get_stack_health",
        lambda force=False: sh.StackHealth(api_up=False, web_up=False),
    )
    monkeypatch.setattr(
        sh,
        "start_calt_stack",
        lambda *a, **k: calls.__setitem__("start", calls["start"] + 1) or True,
    )
    monkeypatch.setattr(
        sh,
        "wait_for_stack",
        lambda **_k: sh.StackHealth(api_up=True, web_up=True),
    )
    monkeypatch.setattr(
        sh,
        "open_url_preferred",
        lambda url: calls.__setitem__("open", calls["open"] + 1) or True,
    )
    monkeypatch.setattr(sh, "local_jarvis_speak", lambda *_a, **_k: "ok")

    ok = sh.open_app_page_guard(
        "/bible",
        health=health,
        on_offer_start=lambda spec: True,
        speak=False,
    )
    assert ok is True
    assert calls["start"] == 1
    assert calls["open"] == 1


def test_open_guard_opens_with_api_warn(monkeypatch):
    sh.reset_cache_for_tests()
    msgs: list[tuple[str, str]] = []
    health = sh.StackHealth(api_up=False, web_up=True)
    with patch.object(sh, "open_url_preferred", return_value=True) as opened:
        ok = sh.open_app_page_guard(
            "http://127.0.0.1:5173/bible",
            health=health,
            on_message=lambda t, b: msgs.append((t, b)),
            on_offer_start=lambda _spec: False,  # Open anyway
            speak=False,
        )
    assert ok is True
    opened.assert_called_once()
    assert msgs and "API" in msgs[0][0]


def test_resolve_open_action_pure():
    assert sh.resolve_open_action(sh.StackHealth(True, True)) == "open"
    assert sh.resolve_open_action(sh.StackHealth(False, True)) == "warn_api_open"
    assert sh.resolve_open_action(sh.StackHealth(False, False)) == "offer_start"
    assert sh.resolve_open_action(sh.StackHealth(False, False), offer_start=False) == "blocked"


def test_down_dialog_spec_start_cancel_labels():
    spec = sh.down_dialog_spec(sh.StackHealth(api_up=False, web_up=False), target_hint="/bible")
    assert spec.primary == "Start CALT stack"
    assert spec.secondary == "Cancel"
    assert "down" in spec.title.lower() or "stack" in spec.title.lower()
    assert "/bible" in spec.body

    web = sh.down_dialog_spec(sh.StackHealth(api_up=True, web_up=False))
    assert web.kind == "web"
    assert web.primary == "Start CALT stack"

    api = sh.down_dialog_spec(sh.StackHealth(api_up=False, web_up=True))
    assert api.kind == "api"
    assert api.secondary == "Open anyway"


def test_resolve_app_url_joins_frontend(monkeypatch):
    monkeypatch.setenv("CALT_FRONTEND_URL", "http://127.0.0.1:5173")
    assert sh.resolve_app_url("/bible") == "http://127.0.0.1:5173/bible"
    assert sh.resolve_app_url("http://example.com/x") == "http://example.com/x"


def test_jarvis_category_for_down():
    assert sh.jarvis_category_for_down("web") == "stack_web_down"
    assert sh.jarvis_category_for_down("api") == "stack_api_down"
    assert sh.jarvis_category_for_down("both") == "stack_both_down"


def test_start_stack_then_open_polls(monkeypatch):
    sh.reset_cache_for_tests()
    opened: list[str] = []
    statuses: list[str] = []
    monkeypatch.setattr(
        sh,
        "get_stack_health",
        lambda force=False: sh.StackHealth(api_up=False, web_up=False),
    )
    monkeypatch.setattr(sh, "start_calt_stack", lambda *a, **k: True)
    monkeypatch.setattr(
        sh,
        "wait_for_stack",
        lambda **_k: sh.StackHealth(api_up=True, web_up=True),
    )
    monkeypatch.setattr(sh, "open_url_preferred", lambda u: opened.append(u) or True)
    monkeypatch.setattr(sh, "local_jarvis_speak", lambda *_a, **_k: "")

    ok = sh.start_stack_then_open("/bible", speak=True, on_status=statuses.append)
    assert ok is True
    assert opened and "bible" in opened[0]
    assert any("Starting" in s for s in statuses)


def test_open_calt_page_opens_when_web_up(monkeypatch):
    sh.reset_cache_for_tests()
    opened: list[str] = []
    starts = {"n": 0}
    monkeypatch.setattr(sh, "open_url_preferred", lambda u: opened.append(u) or True)
    monkeypatch.setattr(sh, "start_calt_stack", lambda *a, **k: starts.__setitem__("n", starts["n"] + 1))
    monkeypatch.setattr(sh, "local_jarvis_speak", lambda *_a, **_k: "")

    ok = sh.open_calt_page(
        "/bible",
        health=sh.StackHealth(api_up=True, web_up=True),
        speak=False,
    )
    assert ok is True
    assert starts["n"] == 0
    assert opened and "bible" in opened[0]


def test_open_calt_page_auto_starts_when_web_down(monkeypatch):
    """Open Bible with stack down → start + poll + open (no dialog / second click)."""
    sh.reset_cache_for_tests()
    calls: dict[str, int] = {"start": 0, "open": 0}
    statuses: list[str] = []
    speaks: list[str] = []

    monkeypatch.setattr(
        sh,
        "get_stack_health",
        lambda force=False: sh.StackHealth(api_up=False, web_up=False),
    )
    monkeypatch.setattr(
        sh,
        "start_calt_stack",
        lambda *a, **k: calls.__setitem__("start", calls["start"] + 1) or True,
    )
    monkeypatch.setattr(
        sh,
        "wait_for_stack",
        lambda **_k: sh.StackHealth(api_up=True, web_up=True),
    )
    monkeypatch.setattr(
        sh,
        "open_url_preferred",
        lambda url: calls.__setitem__("open", calls["open"] + 1) or True,
    )
    monkeypatch.setattr(sh, "local_jarvis_speak", lambda cat, **_k: speaks.append(cat) or cat)

    ok = sh.open_calt_page(
        "/productivity?tab=plan",
        health=sh.StackHealth(api_up=False, web_up=False),
        on_status=statuses.append,
        speak=True,
        auto_start=True,
    )
    assert ok is True
    assert calls["start"] == 1
    assert calls["open"] == 1
    assert "stack_starting" in speaks
    assert "stack_ready" in speaks
    assert any("Starting" in s for s in statuses)


def test_open_calt_page_web_up_api_down_opens_without_start(monkeypatch):
    sh.reset_cache_for_tests()
    opened: list[str] = []
    starts = {"n": 0}
    monkeypatch.setattr(sh, "open_url_preferred", lambda u: opened.append(u) or True)
    monkeypatch.setattr(sh, "start_calt_stack", lambda *a, **k: starts.__setitem__("n", starts["n"] + 1))
    monkeypatch.setattr(sh, "local_jarvis_speak", lambda *_a, **_k: "")

    ok = sh.open_calt_page(
        "/bible",
        health=sh.StackHealth(api_up=False, web_up=True),
        speak=False,
        auto_start=True,
    )
    assert ok is True
    assert starts["n"] == 0
    assert opened


def test_open_calt_page_start_failure_notifies(monkeypatch):
    sh.reset_cache_for_tests()
    msgs: list[tuple[str, str]] = []

    def boom(*_a, **_k) -> bool:
        raise OSError("no run.bat")

    monkeypatch.setattr(
        sh,
        "get_stack_health",
        lambda force=False: sh.StackHealth(api_up=False, web_up=False),
    )
    monkeypatch.setattr(sh, "start_calt_stack", boom)
    monkeypatch.setattr(sh, "local_jarvis_speak", lambda *_a, **_k: "")

    ok = sh.open_calt_page(
        "/bible",
        health=sh.StackHealth(api_up=False, web_up=False),
        on_message=lambda t, b: msgs.append((t, b)),
        speak=False,
        auto_start=True,
    )
    assert ok is False
    assert msgs and "fail" in msgs[0][0].lower()


def test_launch_calt_stack_uses_run_bat():
    from backend.behavior import tracker_launchers as tl
    from backend.paths import ROOT

    assert tl.RUN_APP_BAT == ROOT / "run.bat"
    assert tl.RUN_APP_BAT.is_file()


def test_open_or_focus_calt_debounces(monkeypatch):
    sh.reset_cache_for_tests()
    opens: list[str] = []
    focuses: list[str] = []

    monkeypatch.setattr(sh, "OPEN_DEBOUNCE_S", 15.0)
    monkeypatch.setattr(sh, "open_url_preferred", lambda u: opens.append(u) or True)
    monkeypatch.setattr(
        "backend.behavior.calt_tab_command.request_focus",
        lambda path, force=False: focuses.append(path) or {"ok": True},
    )
    t = {"now": 1000.0}
    monkeypatch.setattr(sh.time, "monotonic", lambda: t["now"])

    assert sh.open_or_focus_calt("/bible") is True
    assert len(opens) == 1
    t["now"] = 1005.0  # within debounce
    assert sh.open_or_focus_calt("/bible") is True
    assert len(opens) == 1  # debounced — no second browser open
    t["now"] = 1020.0
    assert sh.open_or_focus_calt("/bible") is True
    assert len(opens) == 2


def test_start_calt_stack_skips_when_web_up(monkeypatch):
    starts = {"n": 0}
    monkeypatch.setattr(
        sh,
        "get_stack_health",
        lambda force=False: sh.StackHealth(api_up=True, web_up=True),
    )
    monkeypatch.setattr(
        "backend.behavior.tracker_launchers.launch_calt_stack",
        lambda: starts.__setitem__("n", starts["n"] + 1),
    )
    assert sh.start_calt_stack() is False
    assert starts["n"] == 0
    assert sh.start_calt_stack(force=True) is True
    assert starts["n"] == 1

