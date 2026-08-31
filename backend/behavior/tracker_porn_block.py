"""Desktop tracker ↔ device porn hosts sync (porn only — not YouTube)."""

from __future__ import annotations

import logging
import time

log = logging.getLogger("desktop_tracker")

_SYNC_INTERVAL_S = 3600.0
_last_sync_at = 0.0
_last_admin_warn_at = 0.0


def tracker_sync_porn_hosts(*, force_list_refresh: bool = False) -> dict | None:
    """Called from tracker poll — refresh TPD list + write hosts when enabled."""
    global _last_sync_at, _last_admin_warn_at

    now = time.time()
    if not force_list_refresh and now - _last_sync_at < _SYNC_INTERVAL_S:
        return None

    from backend.behavior import device_block as db
    from backend.behavior import porn_blocklist as tpd

    settings = db.load_settings()
    if not settings.get("enabled", True):
        return {"skipped": True, "reason": "disabled"}

    # Ensure list is fresh (weekly) — non-fatal if network blocked.
    list_meta = tpd.refresh_if_stale(force=force_list_refresh)

    _last_sync_at = now
    result = db.apply_from_settings()
    result["list"] = list_meta

    if not result.get("ok") and result.get("needs_admin"):
        if now - _last_admin_warn_at > 6 * 3600:
            _last_admin_warn_at = now
            log.warning(
                "[porn_block] hosts not applied — run scripts\\device_block_apply.bat once as Admin "
                "(tracker will retry hourly). %s domains ready.",
                len(tpd.cached_domains()),
            )
    elif result.get("ok") and result.get("applied"):
        log.info(
            "[porn_block] hosts active — %s porn domains (TPD + defaults)",
            result.get("domain_count"),
        )
    return result
