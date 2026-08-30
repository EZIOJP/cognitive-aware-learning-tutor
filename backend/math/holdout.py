"""
Held-out evaluation split for handwriting samples — never trained or calibrated on.

Assignment is a pure function of ``sample_id``, so a sample's split membership never
changes as the dataset grows. That is what makes the split trustworthy over months of
incremental collection: no re-shuffle can quietly leak an eval sample into training.
The manifest is an audit record of that assignment, not its source of truth.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from typing import Any

from backend.paths import ROOT

HOLDOUT_MANIFEST = ROOT / "data" / "math" / "holdout_manifest.json"
DEFAULT_FRACTION = 0.2
_BUCKETS = 1000


def _bucket(sample_id: str) -> int:
    digest = hashlib.sha1(sample_id.encode("utf-8")).digest()
    return int.from_bytes(digest[:4], "big") % _BUCKETS


def _read_manifest() -> dict[str, Any]:
    if not HOLDOUT_MANIFEST.is_file():
        return {}
    try:
        data = json.loads(HOLDOUT_MANIFEST.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def holdout_fraction() -> float:
    raw = _read_manifest().get("fraction")
    try:
        frac = float(raw)
    except (TypeError, ValueError):
        return DEFAULT_FRACTION
    return frac if 0.0 < frac < 1.0 else DEFAULT_FRACTION


def is_holdout(sample_id: str, *, fraction: float | None = None) -> bool:
    sid = (sample_id or "").strip()
    if not sid:
        return False
    frac = holdout_fraction() if fraction is None else fraction
    return _bucket(sid) < int(round(frac * _BUCKETS))


def split_rows(
    rows: list[dict],
    *,
    fraction: float | None = None,
) -> tuple[list[dict], list[dict]]:
    """Return ``(train_rows, holdout_rows)``."""
    frac = holdout_fraction() if fraction is None else fraction
    train: list[dict] = []
    held: list[dict] = []
    for row in rows:
        sid = (row.get("sample_id") or "").strip()
        (held if is_holdout(sid, fraction=frac) else train).append(row)
    return train, held


def freeze_holdout(
    *,
    fraction: float | None = None,
    user_id: int | None = None,
    rows: list[dict] | None = None,
) -> dict[str, Any]:
    """Record the current split to the manifest so it can be audited and diffed."""
    from backend.math.training_log import _read_rows

    frac = holdout_fraction() if fraction is None else fraction
    data = rows if rows is not None else _read_rows(user_id)
    train, held = split_rows(data, fraction=frac)

    by_tier: dict[str, int] = {}
    for row in held:
        tier = (row.get("tier") or "unknown").strip() or "unknown"
        by_tier[tier] = by_tier.get(tier, 0) + 1

    payload = {
        "frozen_at": datetime.now(UTC).isoformat(),
        "fraction": frac,
        "total_rows": len(data),
        "train_count": len(train),
        "holdout_count": len(held),
        "holdout_by_tier": by_tier,
        "holdout_sample_ids": sorted(
            (r.get("sample_id") or "").strip() for r in held if (r.get("sample_id") or "").strip()
        ),
        "note": (
            "Assignment is sha1(sample_id) % 1000 < fraction*1000 and is stable as the "
            "dataset grows. Changing 'fraction' reassigns samples and invalidates any "
            "baseline measured under the old value."
        ),
    }
    HOLDOUT_MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    HOLDOUT_MANIFEST.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return payload


def holdout_status(*, user_id: int | None = None) -> dict[str, Any]:
    from backend.math.training_log import _read_rows

    rows = _read_rows(user_id)
    train, held = split_rows(rows)
    manifest = _read_manifest()
    return {
        "fraction": holdout_fraction(),
        "total_rows": len(rows),
        "train_count": len(train),
        "holdout_count": len(held),
        "frozen_at": manifest.get("frozen_at", ""),
        "manifest_exists": bool(manifest),
    }
