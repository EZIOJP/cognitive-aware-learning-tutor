"""Desktop tracker ↔ device porn hosts sync — RETIRED (native enforcer owns Device lock)."""

from __future__ import annotations

import logging

log = logging.getLogger("desktop_tracker")

_warned = False


def tracker_sync_porn_hosts(*, force_list_refresh: bool = False) -> dict | None:
    """No-op after 2026-09-13 Device lock native cutover.

    Hosts / settings are owned by calt_enforcer (gateway + elevated CLI).
    Legacy data/behavior/* files are forensics-only.
    """
    global _warned
    _ = force_list_refresh
    if not _warned:
        _warned = True
        log.info(
            "[porn_block] tracker hosts sync retired — use Focus Settings → Filters "
            "(calt_enforcer device_block.*). No Python hosts writes."
        )
    return {"skipped": True, "reason": "native_device_block"}
