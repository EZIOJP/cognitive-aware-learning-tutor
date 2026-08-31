"""Edge-close incident log + playbook (why / how to fix)."""

from __future__ import annotations

from backend.behavior.comms_incidents import (
    announce_edge_event,
    append_incident,
    build_incident,
    compact_incident,
    format_comms_lines,
    last_incident,
    live_issue,
    maybe_announce_edge_gone,
    playbook_for,
)


def test_playbook_both_silent_has_fix():
    why, fix = playbook_for(["both_silent_api_up"])
    assert "stopped polling" in why.lower() or "both stopped" in why.lower()
    assert "edge://extensions" in fix.lower() or "Reload" in fix


def test_playbook_edge_closed_includes_detail():
    why, fix = playbook_for(["both_silent_api_up"], kind="edge_closed")
    assert "closed" in why.lower() or "absent" in why.lower()
    assert "Reload" in fix or "extensions" in fix.lower()


def test_append_incident_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setattr("backend.behavior.comms_incidents._JSONL", tmp_path / "inc.jsonl")
    monkeypatch.setattr("backend.behavior.comms_incidents._LAST_PATH", tmp_path / "inc.json")
    snap = {
        "api_up": True,
        "web_up": True,
        "extension": {
            "status": "dead",
            "selftracker_status": "dead",
            "calt_gate_status": "dead",
            "selftracker_age_s": 400,
            "calt_gate_age_s": 410,
            "cases": ["both_silent_api_up"],
        },
        "dead_strikes": 2,
        "why_rules_idle": ["No extension poll"],
    }
    row = build_incident(kind="edge_closed", snap=snap, extra={"killed_processes": 3})
    assert row["kind"] == "edge_closed"
    assert row["how_to_fix"]
    assert row["facts"]["api_up"] is True
    assert row["facts"]["selftracker_age_s"] == 400
    append_incident(row)
    last = last_incident()
    assert last is not None
    assert last["kind"] == "edge_closed"
    compact = compact_incident(last)
    assert compact is not None
    assert compact["extra"]["killed_processes"] == 3
    log_text = (tmp_path / "inc.jsonl").read_text(encoding="utf-8")
    assert "edge_closed" in log_text
    assert "how_to_fix" in log_text


def test_live_issue_and_format_lines():
    issue = live_issue(["mv3_asleep"])
    assert "sleep" in issue["why"].lower() or "asleep" in issue["why"].lower()
    assert issue["how_to_fix"]
    snap = {
        "api_up": True,
        "web_up": True,
        "startup_grace": False,
        "extension": {
            "status": "stale",
            "selftracker_status": "stale",
            "calt_gate_status": "stale",
            "selftracker_age_s": 90,
            "calt_gate_age_s": 88,
        },
        "current_issue": issue,
        "last_incident": {
            "kind": "edge_closed",
            "why": "Tracker closed Microsoft Edge because extensions were confirmed absent.",
            "how_to_fix": "Reload both extensions.",
        },
    }
    lines = format_comms_lines(snap)
    joined = "\n".join(lines)
    assert "ST stale (90s)" in joined
    assert "Gate stale (88s)" in joined
    assert "Why:" in joined
    assert "Last Edge close:" in joined
    assert "Fix:" in joined


def test_snapshot_exposes_current_issue(tmp_path, monkeypatch):
    monkeypatch.setattr("backend.behavior.comms_health._STATE_PATH", tmp_path / "comms.json")
    monkeypatch.setattr("backend.behavior.comms_incidents._JSONL", tmp_path / "inc.jsonl")
    monkeypatch.setattr("backend.behavior.comms_incidents._LAST_PATH", tmp_path / "inc.json")
    from backend.behavior.comms_health import snapshot

    snap = snapshot(api_up=True, web_up=True)
    assert "current_issue" in snap
    assert snap["current_issue"]["how_to_fix"]
    assert "last_incident" in snap


def test_playbook_edge_quit_mentions_crash_and_reload():
    why, fix = playbook_for(["mv3_asleep"], kind="edge_quit")
    assert "crash" in why.lower() or "quit" in why.lower()
    assert "tracker did not" in why.lower() or "on its own" in why.lower()
    assert "Reload" in fix or "extensions" in fix.lower()
    assert "Errors" in fix or "errors" in fix.lower()


def test_format_lines_include_last_quit():
    issue = live_issue(["mv3_asleep"])
    snap = {
        "api_up": True,
        "web_up": True,
        "extension": {
            "status": "stale",
            "selftracker_status": "alive",
            "calt_gate_status": "stale",
            "selftracker_age_s": 8,
            "calt_gate_age_s": 90,
        },
        "current_issue": issue,
        "last_incident": {
            "kind": "edge_quit",
            "why": "Edge quit or crashed on its own.",
            "how_to_fix": "Reload both extensions. Click Errors.",
        },
    }
    joined = "\n".join(format_comms_lines(snap))
    assert "Last Edge close:" in joined
    assert "quit" in joined.lower() or "crash" in joined.lower()


def test_announce_edge_event_calls_show_not_tk(monkeypatch):
    shown: list[tuple[str, str, str]] = []
    spoken: list[str] = []
    monkeypatch.setattr(
        "backend.behavior.comms_incidents._show_notice",
        lambda why, fix, **kw: shown.append((why, fix, str(kw.get("title") or ""))),
    )
    monkeypatch.setattr(
        "backend.behavior.gate_alerts.speak_alert",
        lambda text, force=False: spoken.append(text),
    )
    row = {
        "kind": "edge_quit",
        "why": "Edge quit or crashed on its own — Gate SW was Inactive.",
        "how_to_fix": "Reload both. Click Errors. Do not close Edge.",
    }
    announce_edge_event(row)
    assert shown, "notice window path must run even without a display"
    assert "quit" in shown[0][0].lower() or "crash" in shown[0][0].lower()
    assert shown[0][1]
    assert spoken and "Edge" in spoken[0]


def test_maybe_announce_edge_gone_logs_jsonl(tmp_path, monkeypatch):
    monkeypatch.setattr("backend.behavior.comms_health._STATE_PATH", tmp_path / "comms.json")
    monkeypatch.setattr("backend.behavior.comms_incidents._JSONL", tmp_path / "inc.jsonl")
    monkeypatch.setattr("backend.behavior.comms_incidents._LAST_PATH", tmp_path / "inc.json")
    announced: list[dict] = []
    monkeypatch.setattr(
        "backend.behavior.comms_incidents.announce_edge_event",
        lambda row: announced.append(row),
    )
    assert maybe_announce_edge_gone(running=True) is None
    row = maybe_announce_edge_gone(running=False)
    assert row is not None
    assert row["kind"] == "edge_quit"
    assert last_incident()["kind"] == "edge_quit"
    log_text = (tmp_path / "inc.jsonl").read_text(encoding="utf-8")
    assert "edge_quit" in log_text
    assert announced and announced[0]["kind"] == "edge_quit"
    # No second spam on the same falling edge
    assert maybe_announce_edge_gone(running=False) is None
