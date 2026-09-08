"""Gate notify / singleflight / 5‑minute heartbeat helpers."""

from __future__ import annotations

import threading
import time

from backend.behavior.browser_gate_policy import build_browser_gate_section
from backend.behavior.gate_notify import (
    current_policy_gen,
    invalidate_gate_cache,
    run_singleflight,
)


def test_build_browser_gate_section_poll_is_five_minutes():
    section = build_browser_gate_section(
        enabled=True,
        locked=True,
        morning_next="bible",
    )
    assert section["intervals"]["extension_gate_poll_s"] == 300
    assert section["intervals"]["extension_gate_idle_alarm_min"] == 5


def test_invalidate_bumps_policy_gen_and_clears_cache():
    from backend.behavior import distraction_gate as dg

    uid = 424242
    dg._gate_payload_cache[uid] = (time.monotonic(), {"ok": True})
    before = current_policy_gen(uid)
    gen = invalidate_gate_cache(uid, reason="unit_test")
    assert gen == before + 1
    assert uid not in dg._gate_payload_cache
    assert current_policy_gen(uid) == gen


def test_singleflight_coalesces_concurrent_computes():
    calls = {"n": 0}
    barrier = threading.Barrier(4)

    def compute():
        calls["n"] += 1
        time.sleep(0.05)
        return {"n": calls["n"]}

    results: list[dict] = []

    def worker():
        barrier.wait()
        results.append(run_singleflight(777001, compute))

    threads = [threading.Thread(target=worker) for _ in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=5)
    assert len(results) == 4
    assert calls["n"] == 1
    assert all(r["n"] == 1 for r in results)


def test_singleflight_waiter_serves_stale_on_timeout():
    barrier = threading.Barrier(2)
    stale = {"ok": True, "stale": True}

    def compute():
        barrier.wait()
        time.sleep(0.35)
        return {"ok": True, "fresh": True}

    def leader():
        run_singleflight(777002, compute, waiter_timeout=0.05)

    t = threading.Thread(target=leader)
    t.start()
    barrier.wait()
    out = run_singleflight(
        777002,
        compute,
        stale_fallback=lambda: stale,
        waiter_timeout=0.05,
    )
    t.join(timeout=2)
    assert out == stale
