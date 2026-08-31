"""Cross-client comms health — false positives, false negatives, Edge policy.

Sources
-------
- SelfTracker and CALT Gate are tracked **separately**. One alive is enough
  to keep Edge open (partial miss ≠ uninstall).
- SPA / dashboard polls without ``X-CALT-Extension`` never count.

Statuses
--------
unknown  never seen
alive    last ping ≤ ALIVE_S
stale    MV3 sleep, API down, or startup grace — **never close Edge**
dead     both known sources silent while API has been up past grace
pending  dead once — need a second tracker poll before close (two-strike)

Close Edge only when: dead + two-strike + API up + not free-mode + grace over.
"""

from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from typing import Any

from backend.paths import ROOT

_STATE_PATH = ROOT / "data" / "behavior" / "comms_health.json"
_lock = threading.Lock()

# Gate poll ~8–12s; telemetry ~90s; MV3 SW sleep ~30–60s.
ALIVE_S = 40.0
STALE_S = 180.0
DEAD_S = 180.0
# After API/tracker comes back, extensions need time to poll again.
STARTUP_GRACE_S = 90.0
# Circuit breaker cooldowns in extensions: 30s (gate) / 180s (selftracker).
CIRCUIT_EXPIRE_S = 200.0
# Two consecutive *tracker* observations of dead before closing Edge.
DEAD_STRIKES_NEEDED = 2
WATCH_STALE_S = 36 * 3600.0
# Don't re-popup if tracker already announced a close, or Edge flaps.
GONE_NOTICE_COOLDOWN_S = 300.0
GONE_SKIP_AFTER_CLOSE_S = 120.0

_EMPTY: dict[str, Any] = {
    "sources": {},
    "extension": {},
    "tracker": {},
    "watch": {},
}

_GATE_FAMILY = ("calt-gate", "calt-gate-locked")
_TRACKER_FAMILY = ("selftracker", "selftracker-locked")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime | None) -> str | None:
    return dt.isoformat() if dt else None


def _parse_iso(raw: Any) -> datetime | None:
    if not raw:
        return None
    try:
        dt = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except (TypeError, ValueError):
        return None


def _read() -> dict[str, Any]:
    try:
        if _STATE_PATH.is_file():
            raw = json.loads(_STATE_PATH.read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                return raw
    except Exception:
        pass
    return json.loads(json.dumps(_EMPTY))


def _write(data: dict[str, Any]) -> None:
    try:
        _STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
        _STATE_PATH.write_text(json.dumps(data, indent=2), encoding="utf-8")
    except Exception:
        pass


def _family(source: str) -> str:
    s = (source or "").strip().lower()
    if s in _GATE_FAMILY or s.startswith("calt-gate"):
        return "calt-gate"
    if s in _TRACKER_FAMILY or s.startswith("selftracker"):
        return "selftracker"
    return s or "extension"


def _age_s(iso: str | None, now: datetime) -> float | None:
    dt = _parse_iso(iso)
    if not dt:
        return None
    delta = (now - dt).total_seconds()
    # Clock skew: future timestamps would look "negative age" / dead. Clamp to alive.
    if delta < 0:
        return 0.0
    return delta


def note_extension_from_request(request: Any, *, server_mode: str | None = None) -> None:
    """Only count polls that send X-CALT-Extension (SPA/dashboard must not fake alive)."""
    try:
        headers = request.headers
    except Exception:
        return
    source = (headers.get("x-calt-extension") or "").strip()
    if not source:
        return
    circuit = str(headers.get("x-calt-ext-circuit") or "").strip().lower() in ("1", "true", "yes")
    paused = str(headers.get("x-calt-ext-paused") or "").strip().lower() in ("1", "true", "yes")
    cached = (headers.get("x-calt-ext-mode") or "").strip() or None
    note_extension_heartbeat(
        source=source,
        server_mode=server_mode,
        cached_mode=cached,
        circuit_breaker=circuit,
        redirects_paused=paused or circuit,
    )


def note_extension_heartbeat(
    *,
    source: str,
    server_mode: str | None = None,
    cached_mode: str | None = None,
    circuit_breaker: bool = False,
    redirects_paused: bool = False,
    extra: dict[str, Any] | None = None,
) -> None:
    """Record a real extension poll (header X-CALT-Extension required at call site)."""
    src = (source or "extension").strip()[:40]
    family = _family(src)
    now_iso = _iso(_now())
    with _lock:
        state = _read()
        sources = dict(state.get("sources") or {})
        row = dict(sources.get(family) or {})
        row["last_seen_at"] = now_iso
        row["raw_source"] = src
        sources[family] = row
        state["sources"] = sources

        ext = dict(state.get("extension") or {})
        ext.update(
            {
                "last_seen_at": now_iso,
                "source": src,
                "family": family,
                "server_mode": (server_mode or "")[:24] or None,
                "cached_mode": (cached_mode or "")[:24] or None,
                "circuit_breaker": bool(circuit_breaker),
                "redirects_paused": bool(redirects_paused or circuit_breaker),
            }
        )
        if circuit_breaker or redirects_paused:
            ext["circuit_since"] = now_iso
        elif not circuit_breaker and not redirects_paused:
            ext.pop("circuit_since", None)
        if extra:
            for k, v in extra.items():
                if k in ("last_seen_at", "source"):
                    continue
                ext[k] = v
        state["extension"] = ext
        state["dead_strikes"] = 0
        _write(state)


def note_tracker_tick(*, alive: bool = True) -> None:
    now_iso = _iso(_now())
    with _lock:
        state = _read()
        tr = dict(state.get("tracker") or {})
        if not tr.get("started_at"):
            tr["started_at"] = now_iso
        tr["last_seen_at"] = now_iso
        tr["alive"] = bool(alive)
        state["tracker"] = tr
        _write(state)


def note_watch_ingest(*, source: str | None = None) -> None:
    with _lock:
        state = _read()
        state["watch"] = {
            "last_seen_at": _iso(_now()),
            "source": (source or "wearables")[:40],
        }
        _write(state)


def note_api_up_transition(*, api_up: bool) -> None:
    """Call when stack health is known — arms startup grace after API recovery."""
    with _lock:
        state = _read()
        was = state.get("api_was_up")
        if api_up and was is False:
            state["api_recovered_at"] = _iso(_now())
        if api_up and was is None:
            # First observation this process — still grace so a bounce isn't a close.
            state.setdefault("api_recovered_at", _iso(_now()))
        state["api_was_up"] = bool(api_up)
        _write(state)


def _circuit_still_active(ext: dict[str, Any], now: datetime) -> bool:
    if not (ext.get("circuit_breaker") or ext.get("redirects_paused")):
        return False
    age = _age_s(ext.get("circuit_since") or ext.get("last_seen_at"), now)
    if age is None:
        return True
    return age <= CIRCUIT_EXPIRE_S


def classify_extension(
    *,
    age_s: float | None,
    api_up: bool,
    circuit_breaker: bool,
    redirects_paused: bool,
    server_mode: str | None,
    cached_mode: str | None,
    selftracker_age_s: float | None = None,
    calt_gate_age_s: float | None = None,
    startup_grace: bool = False,
    browser_mode: str | None = None,
    circuit_expired: bool = False,
    ever_seen: bool | None = None,
) -> dict[str, Any]:
    """Pure classifier — used by tests and snapshot()."""
    reasons: list[str] = []
    false_positives: list[str] = []
    false_negatives: list[str] = []
    cases: list[str] = []

    st_age = selftracker_age_s
    gt_age = calt_gate_age_s
    # Combined age = most recent family ping.
    ages = [a for a in (age_s, st_age, gt_age) if a is not None]
    combined = min(ages) if ages else age_s

    def _status_for(a: float | None) -> str:
        if a is None:
            return "unknown"
        if a <= ALIVE_S:
            return "alive"
        if a <= STALE_S:
            return "stale"
        if not api_up:
            return "stale"
        return "dead"

    st_status = _status_for(st_age)
    gt_status = _status_for(gt_age)

    if combined is None and ever_seen is False:
        status = "unknown"
        reasons.append("No extension heartbeat yet (need X-CALT-Extension on gate poll).")
        cases.append("never_seen")
    elif combined is None:
        status = "unknown"
        reasons.append("No extension heartbeat yet (need X-CALT-Extension on gate poll).")
        cases.append("never_seen")
    elif combined <= ALIVE_S:
        status = "alive"
        cases.append("fresh_poll")
    elif combined <= STALE_S:
        status = "stale"
        reasons.append(
            f"Extension silent {int(combined)}s — MV3 service worker may be asleep, not uninstalled."
        )
        false_negatives.append("dead_while_asleep")
        cases.append("mv3_asleep")
    elif not api_up:
        status = "stale"
        reasons.append("API is down — extension cannot heartbeat; do not treat as uninstalled.")
        false_negatives.append("dead_while_api_down")
        cases.append("api_down_silent")
    elif startup_grace:
        status = "stale"
        reasons.append("API/tracker just came back — wait for extensions to poll before judging dead.")
        false_negatives.append("dead_during_startup_grace")
        cases.append("startup_grace")
    else:
        status = "dead"
        reasons.append(
            f"No extension poll for {int(combined)}s while API is up — SelfTracker/CALT Gate likely unloaded."
        )
        cases.append("both_silent_api_up")

    # Partial: one family alive, the other dead — do not close Edge.
    if st_status == "alive" and gt_status == "dead":
        status = "alive"
        reasons.append("CALT Gate silent but SelfTracker is polling — treat as alive (partial).")
        false_positives.append("one_extension_dead")
        cases.append("partial_gate_dead")
    elif gt_status == "alive" and st_status == "dead":
        status = "alive"
        reasons.append("SelfTracker silent but CALT Gate is polling — treat as alive (partial).")
        false_positives.append("one_extension_dead")
        cases.append("partial_selftracker_dead")
    elif st_status == "alive" or gt_status == "alive":
        status = "alive"

    circuit_on = (circuit_breaker or redirects_paused) and not circuit_expired
    if status == "alive" and circuit_on:
        reasons.append("Circuit breaker paused redirects — rules look 'off' but Edge must stay open.")
        false_positives.append("alive_but_not_enforcing")
        cases.append("circuit_breaker")
    if circuit_expired and (circuit_breaker or redirects_paused):
        cases.append("circuit_expired")

    sm = (server_mode or "").strip().lower()
    cm = (cached_mode or "").strip().lower()
    if sm and cm and sm != cm:
        reasons.append(f"Mode mismatch: API={sm} extension-cache={cm} (rules lag until next poll).")
        false_positives.append("mode_mismatch")
        cases.append("mode_mismatch")

    mode = (browser_mode or sm or "").strip().lower()
    free_mode = mode in ("free", "open")

    may_close_edge = status == "dead" and api_up and not startup_grace and not free_mode
    if free_mode and status == "dead":
        may_close_edge = False
        reasons.append("Free browsing mode — do not close Edge even if extension looks dead.")
        cases.append("free_mode_hold")

    may_open_edge = status != "alive"
    return {
        "status": status,
        "age_s": None if combined is None else round(combined, 1),
        "selftracker_status": st_status,
        "calt_gate_status": gt_status,
        "may_close_edge": may_close_edge,
        "may_open_edge": may_open_edge,
        "reasons": reasons,
        "false_positives": false_positives,
        "false_negatives": false_negatives,
        "cases": cases,
    }


def _startup_grace(state: dict[str, Any], now: datetime) -> bool:
    for key in ("api_recovered_at",):
        age = _age_s(state.get(key), now)
        if age is not None and age < STARTUP_GRACE_S:
            return True
    started = _age_s((state.get("tracker") or {}).get("started_at"), now)
    if started is not None and started < STARTUP_GRACE_S:
        return True
    return False


def snapshot(*, api_up: bool | None = None, web_up: bool | None = None) -> dict[str, Any]:
    """Compact comms block for day-status / tracker board."""
    if api_up is None or web_up is None:
        try:
            from backend.behavior.stack_health import get_stack_health

            h = get_stack_health(force=False)
            api_up = h.api_up if api_up is None else api_up
            web_up = h.web_up if web_up is None else web_up
        except Exception:
            api_up = bool(api_up)
            web_up = bool(web_up)

    now = _now()
    with _lock:
        state = _read()
        # Persist API transition without nested lock.
        was = state.get("api_was_up")
        if api_up and was is False:
            state["api_recovered_at"] = _iso(now)
        if api_up and was is None:
            state.setdefault("api_recovered_at", _iso(now))
        state["api_was_up"] = bool(api_up)
        _write(state)

    ext = dict(state.get("extension") or {})
    tracker = dict(state.get("tracker") or {})
    watch = dict(state.get("watch") or {})
    sources = dict(state.get("sources") or {})
    st_age = _age_s((sources.get("selftracker") or {}).get("last_seen_at"), now)
    gt_age = _age_s((sources.get("calt-gate") or {}).get("last_seen_at"), now)
    ext_age = _age_s(ext.get("last_seen_at"), now)
    grace = _startup_grace(state, now)
    circuit_on = _circuit_still_active(ext, now)
    circuit_expired = bool(
        (ext.get("circuit_breaker") or ext.get("redirects_paused")) and not circuit_on
    )

    classified = classify_extension(
        age_s=ext_age,
        api_up=bool(api_up),
        circuit_breaker=bool(ext.get("circuit_breaker")),
        redirects_paused=bool(ext.get("redirects_paused")),
        server_mode=ext.get("server_mode"),
        cached_mode=ext.get("cached_mode"),
        selftracker_age_s=st_age,
        calt_gate_age_s=gt_age,
        startup_grace=grace,
        browser_mode=ext.get("server_mode"),
        circuit_expired=circuit_expired,
        ever_seen=bool(ext.get("last_seen_at") or sources),
    )

    why_rules = list(classified["reasons"])
    if not api_up:
        why_rules.append("API down — gate poll fails; cached extension rules go stale.")
    if not web_up:
        why_rules.append("Web UI down — FOCUS tab command cannot land in CALT.")
    watch_age = _age_s(watch.get("last_seen_at"), now)
    if watch_age is not None and watch_age > WATCH_STALE_S:
        why_rules.append("Watch ingest is stale (>36h) — recovery hint may be yesterday's sleep.")
        classified["false_negatives"] = list(classified["false_negatives"]) + ["watch_stale"]

    strikes = int(state.get("dead_strikes") or 0)
    close_ready = bool(classified["may_close_edge"] and strikes >= DEAD_STRIKES_NEEDED)
    if classified["may_close_edge"] and strikes < DEAD_STRIKES_NEEDED:
        classified["cases"] = list(classified["cases"]) + ["two_strike_pending"]
        why_rules.append(
            f"Dead observation {strikes}/{DEAD_STRIKES_NEEDED} — Edge stays until a second confirm."
        )

    last = None
    current = None
    try:
        from backend.behavior.comms_incidents import compact_incident, last_incident as _last_inc, live_issue

        last = compact_incident(_last_inc())
        current = live_issue(list(classified.get("cases") or []))
    except Exception:
        last = None
        current = None

    return {
        "generated_at": _iso(now),
        "api_up": bool(api_up),
        "web_up": bool(web_up),
        "startup_grace": grace,
        "extension": {
            **classified,
            "source": ext.get("source"),
            "last_seen_at": ext.get("last_seen_at"),
            "server_mode": ext.get("server_mode"),
            "cached_mode": ext.get("cached_mode"),
            "circuit_breaker": circuit_on,
            "selftracker_age_s": None if st_age is None else round(st_age, 1),
            "calt_gate_age_s": None if gt_age is None else round(gt_age, 1),
        },
        "tracker": {
            "last_seen_at": tracker.get("last_seen_at"),
            "age_s": None if _age_s(tracker.get("last_seen_at"), now) is None
            else round(_age_s(tracker.get("last_seen_at"), now) or 0, 1),
            "alive": bool(tracker.get("alive")),
            "started_at": tracker.get("started_at"),
        },
        "watch": {
            "last_seen_at": watch.get("last_seen_at"),
            "age_s": None if watch_age is None else round(watch_age, 1),
            "source": watch.get("source"),
        },
        "why_rules_idle": why_rules,
        "dead_strikes": strikes,
        "last_edge_close_at": state.get("last_edge_close_at"),
        "current_issue": current,
        "last_incident": last,
        "edge_policy": {
            "close_only_if_extension_dead": True,
            "may_close_edge": close_ready,
            "may_close_candidate": classified["may_close_edge"],
            "may_open_new_window": classified["may_open_edge"],
            "two_strike": DEAD_STRIKES_NEEDED,
        },
    }


def mark_edge_closed() -> None:
    with _lock:
        state = _read()
        state["last_edge_close_at"] = _iso(_now())
        state["edge_running"] = False
        state["dead_strikes"] = 0
        _write(state)


def observe_edge_presence(running: bool) -> bool:
    """Record whether msedge.exe is running. True = falling edge that needs a notice.

    First 'not running' with a fresh extension ping also fires (crash during
    tracker restart). Never fires merely because Edge was already gone overnight.
    """
    now = _now()
    with _lock:
        state = _read()
        was = state.get("edge_running")
        state["edge_running"] = bool(running)

        def _should_skip() -> bool:
            close_age = _age_s(state.get("last_edge_close_at"), now)
            gone_age = _age_s(state.get("last_edge_gone_at"), now)
            if close_age is not None and close_age < GONE_SKIP_AFTER_CLOSE_S:
                return True
            if gone_age is not None and gone_age < GONE_NOTICE_COOLDOWN_S:
                return True
            return False

        fire = False
        if was is True and not running:
            fire = not _should_skip()
        elif was is None and not running:
            sources = dict(state.get("sources") or {})
            ages = []
            for fam in ("selftracker", "calt-gate"):
                a = _age_s((sources.get(fam) or {}).get("last_seen_at"), now)
                if a is not None:
                    ages.append(a)
            recent = bool(ages) and min(ages) < STALE_S
            fire = recent and not _should_skip()
        if fire:
            state["last_edge_gone_at"] = _iso(now)
        _write(state)
        return fire


def edge_close_cooldown_ok(*, min_gap_s: float = 300.0) -> bool:
    with _lock:
        state = _read()
    age = _age_s(state.get("last_edge_close_at"), _now())
    return age is None or age >= min_gap_s


def record_dead_strike(*, is_dead_candidate: bool) -> int:
    """Increment two-strike counter only on tracker close-evaluation path."""
    with _lock:
        state = _read()
        if not is_dead_candidate:
            state["dead_strikes"] = 0
            _write(state)
            return 0
        n = int(state.get("dead_strikes") or 0) + 1
        state["dead_strikes"] = n
        _write(state)
        return n


def extension_heartbeat_age_s() -> float | None:
    with _lock:
        state = _read()
    now = _now()
    sources = state.get("sources") or {}
    ages = []
    for fam in ("selftracker", "calt-gate"):
        a = _age_s((sources.get(fam) or {}).get("last_seen_at"), now)
        if a is not None:
            ages.append(a)
    if ages:
        return min(ages)
    return _age_s((state.get("extension") or {}).get("last_seen_at"), now)


def extension_is_alive() -> bool:
    """True only on a fresh gate/telemetry ping — does not probe the API (no recursion)."""
    age = extension_heartbeat_age_s()
    return age is not None and age <= ALIVE_S


def may_close_edge(*, api_up: bool, browser_mode: str | None = None) -> bool:
    """Close Edge only when confirmed dead (two-strike applied by close_edge path)."""
    snap = snapshot(api_up=api_up, web_up=True)
    if browser_mode and str(browser_mode).lower() in ("free", "open"):
        return False
    return bool(snap.get("edge_policy", {}).get("may_close_candidate"))


def may_open_new_edge_window() -> bool:
    """False when the extension is actively polling — never spawn a second Edge."""
    return not extension_is_alive()
