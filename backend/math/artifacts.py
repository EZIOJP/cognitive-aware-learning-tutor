"""Timestamped snapshots of trained artifacts, taken before they are overwritten."""

from __future__ import annotations

import logging
import shutil
from datetime import UTC, datetime
from pathlib import Path

from backend.paths import ROOT

logger = logging.getLogger(__name__)

SNAPSHOT_DIR = ROOT / "data" / "math" / "artifact_snapshots"
KEEP_DEFAULT = 5


def _prune(bucket: Path, keep: int) -> None:
    """Drop all but the newest ``keep`` snapshots; names sort chronologically."""
    try:
        entries = sorted((p for p in bucket.iterdir() if p.is_file()), reverse=True)
    except OSError:
        return
    for stale in entries[max(keep, 1) :]:
        try:
            stale.unlink()
        except OSError:
            logger.warning("could not prune snapshot %s", stale)


def snapshot_artifact(path: Path, *, keep: int = KEEP_DEFAULT) -> Path | None:
    """
    Copy ``path`` into ``artifact_snapshots/<stem>/`` so an overwrite can be undone.

    Returns the snapshot path, or None when there was nothing to copy. Never raises:
    a failed snapshot must not block the retrain that asked for it.
    """
    if not path.is_file():
        return None
    bucket = SNAPSHOT_DIR / path.stem
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
    try:
        bucket.mkdir(parents=True, exist_ok=True)
        dest = bucket / f"{stamp}{path.suffix}"
        # Two saves inside the same clock tick must not clobber each other.
        collision = 0
        while dest.exists():
            collision += 1
            dest = bucket / f"{stamp}-{collision}{path.suffix}"
        shutil.copy2(path, dest)
    except OSError as e:
        logger.warning("artifact snapshot failed for %s: %s", path, e)
        return None
    _prune(bucket, keep)
    return dest


def list_snapshots(path: Path) -> list[Path]:
    """Newest-first snapshots taken for ``path``."""
    bucket = SNAPSHOT_DIR / path.stem
    if not bucket.is_dir():
        return []
    return sorted((p for p in bucket.iterdir() if p.is_file()), reverse=True)


def restore_latest(path: Path) -> Path | None:
    """Roll ``path`` back to its most recent snapshot."""
    snaps = list_snapshots(path)
    if not snaps:
        return None
    snapshot_artifact(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(snaps[0], path)
    return path
