"""Log structure verification mismatches for fraction-guard tuning (Phase E)."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from backend.paths import ROOT

LOG_PATH = ROOT / "data" / "math" / "structure_misseg_log.jsonl"


def log_mismatch(
    *,
    latex: str,
    reason: str,
    geometry_notes: list[str] | None = None,
    band_bbox: dict[str, float] | None = None,
) -> None:
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    entry: dict[str, Any] = {
        "timestamp": datetime.now(UTC).isoformat(),
        "latex": (latex or "")[:200],
        "reason": reason,
        "geometry_notes": geometry_notes or [],
        "band_bbox": band_bbox,
    }
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")


def read_recent(limit: int = 50) -> list[dict[str, Any]]:
    if not LOG_PATH.is_file():
        return []
    lines = LOG_PATH.read_text(encoding="utf-8").strip().splitlines()
    out: list[dict[str, Any]] = []
    for line in lines[-limit:]:
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return out


def fraction_mismatch_count() -> int:
    return sum(1 for e in read_recent(500) if "fraction" in (e.get("reason") or ""))
