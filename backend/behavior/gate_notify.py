"""Gate cache invalidation, singleflight, and WebSocket fanout for GATE_CHANGED.

Mature control-plane helpers: clients use a slow 5‑minute heartbeat; rule
changes push an immediate refresh so SoftLand/DNR never sit on stale policy.
"""

from __future__ import annotations

import asyncio
import concurrent.futures
import logging
import threading
import time
from typing import Any, Callable

from fastapi import WebSocket

log = logging.getLogger("calt.gate_notify")

_lock = threading.Lock()
_policy_gen: dict[int, int] = {}
_futures: dict[int, concurrent.futures.Future] = {}

_ws_lock = asyncio.Lock()
_gate_sockets: dict[int, set[WebSocket]] = {}


def current_policy_gen(user_id: int) -> int:
    with _lock:
        return int(_policy_gen.get(int(user_id), 0))


def bump_policy_gen(user_id: int) -> int:
    uid = int(user_id)
    with _lock:
        n = int(_policy_gen.get(uid, 0)) + 1
        _policy_gen[uid] = n
        return n


def invalidate_gate_cache(user_id: int, *, reason: str = "") -> int:
    """Drop TTL caches and bump generation so the next GET recomputes."""
    from backend.behavior import distraction_gate as dg

    uid = int(user_id)
    gen = bump_policy_gen(uid)
    dg._gate_payload_cache.pop(uid, None)
    dg._nudge_cache.pop(uid, None)
    log.info("gate invalidated user=%s gen=%s reason=%s", uid, gen, reason or "-")
    try:
        schedule_gate_changed(uid, reason=reason or "invalidate")
    except Exception as exc:  # noqa: BLE001
        log.debug("gate notify schedule failed: %s", exc)
    return gen


def schedule_gate_changed(user_id: int, *, reason: str = "") -> None:
    """Fire-and-forget WS fanout from sync request handlers."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return
    loop.create_task(broadcast_gate_changed(user_id, reason=reason))


async def register_gate_socket(user_id: int, websocket: WebSocket) -> None:
    uid = int(user_id)
    async with _ws_lock:
        _gate_sockets.setdefault(uid, set()).add(websocket)


async def unregister_gate_socket(user_id: int, websocket: WebSocket) -> None:
    uid = int(user_id)
    async with _ws_lock:
        socks = _gate_sockets.get(uid)
        if not socks:
            return
        socks.discard(websocket)
        if not socks:
            _gate_sockets.pop(uid, None)


async def broadcast_gate_changed(user_id: int, *, reason: str = "") -> None:
    uid = int(user_id)
    payload = {
        "type": "GATE_CHANGED",
        "user_id": uid,
        "policy_gen": current_policy_gen(uid),
        "reason": reason or "invalidate",
        "ts": int(time.time() * 1000),
    }
    async with _ws_lock:
        socks = list(_gate_sockets.get(uid) or ())
    dead: list[WebSocket] = []
    for ws in socks:
        try:
            await ws.send_json(payload)
        except Exception:
            dead.append(ws)
    if dead:
        async with _ws_lock:
            live = _gate_sockets.get(uid)
            if live:
                for ws in dead:
                    live.discard(ws)
                if not live:
                    _gate_sockets.pop(uid, None)


def has_inflight(user_id: int) -> bool:
    with _lock:
        return int(user_id) in _futures


def run_singleflight(
    user_id: int,
    compute: Callable[[], dict[str, Any]],
    *,
    stale_fallback: Callable[[], dict[str, Any] | None] | None = None,
    waiter_timeout: float = 8.0,
) -> dict[str, Any]:
    """One in-flight compute per user; waiters share the same Future result.

    Waiters time out quickly and prefer a stale payload over hanging the API
    (SoftLand / extension polls must stay responsive under SQLite pile-up).
    """
    uid = int(user_id)
    with _lock:
        fut = _futures.get(uid)
        if fut is None:
            fut = concurrent.futures.Future()
            _futures[uid] = fut
            leader = True
        else:
            leader = False

    if leader:
        try:
            fut.set_result(compute())
        except BaseException as exc:  # noqa: BLE001
            fut.set_exception(exc)
        finally:
            with _lock:
                if _futures.get(uid) is fut:
                    _futures.pop(uid, None)
        return fut.result()

    try:
        return fut.result(timeout=waiter_timeout)
    except concurrent.futures.TimeoutError:
        if stale_fallback is not None:
            stale = stale_fallback()
            if stale is not None:
                log.warning(
                    "gate singleflight timeout user=%s; serving stale cache",
                    uid,
                )
                return stale
        raise
