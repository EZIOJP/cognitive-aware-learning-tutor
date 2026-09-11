"""Single Python door to the calt_enforcer command gateway (Phase 2 / P5)."""

from __future__ import annotations

import json
import logging
import time
from typing import Any

PIPE = r"\\.\pipe\calt_enforcer_cmd"
logger = logging.getLogger(__name__)


class GatewayUnavailable(RuntimeError):
    """calt_enforcer is not running, or the pipe refused the connection."""


def gateway_call(op: str, payload: dict | None = None, *, timeout: float = 3.0) -> dict[str, Any]:
    """Send one op to ``\\\\.\\pipe\\calt_enforcer_cmd`` and return the parsed reply.

    Framing matches ``scripts/desktop_tracker/run/gateway_cmd.ps1``: raw UTF-8
    JSON request/response (no length prefix). Retries briefly because the
    enforcer recycles the single pipe instance between clients.
    """
    req = json.dumps(
        {"v": 1, "id": "py", "op": op, "payload": payload or {}},
        separators=(",", ":"),
    )
    last: Exception | None = None
    for attempt in range(3):
        try:
            with open(PIPE, "r+b", buffering=0) as pipe:
                pipe.write(req.encode("utf-8"))
                raw = pipe.read(64 * 1024)
            try:
                return json.loads(raw.decode("utf-8", "replace") or "{}")
            except ValueError as exc:
                raise GatewayUnavailable(f"bad reply: {raw!r}") from exc
        except OSError as exc:
            last = exc
            if attempt < 2:
                time.sleep(0.12)
                continue
            raise GatewayUnavailable(str(exc)) from exc
    raise GatewayUnavailable(str(last) if last else "gateway unavailable")
