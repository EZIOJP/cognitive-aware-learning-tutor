"""Gap-driven lazy ingest for deferred raw_library books."""

from __future__ import annotations

import logging
import re
import shutil
from typing import Any

from backend.corpus.jobs import get_job, start_job
from backend.corpus.library import SUBJECT_CATALOG, ingest_subject, scan_book_slot

log = logging.getLogger(__name__)

TOPIC_SUBJECT_MAP: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"statistic|hypothesis|p-value|regression", re.I), "statistics"),
    (re.compile(r"python|pandas|data\s*science|from\s*scratch", re.I), "foundations"),
    (re.compile(r"pipeline|deployment|ml\s*system|serving", re.I), "ml_systems"),
    (re.compile(r"artificial\s*intelligence|thinking\s*human|agi", re.I), "ai_context"),
]


def subject_for_gap_topic(topic: str) -> str | None:
    for pattern, subject_id in TOPIC_SUBJECT_MAP:
        if pattern.search(topic):
            return subject_id
    return None


def pandoc_available() -> bool:
    return shutil.which("pandoc") is not None


def trigger_gap_ingest_for_gaps(gaps: list[dict[str, Any]]) -> list[str]:
    """Start background ingest for high-severity gaps when book is on disk."""
    triggered: list[str] = []
    existing = get_job()
    if existing and existing.status == "running":
        return triggered

    for gap in gaps:
        if gap.get("severity") != "high":
            continue
        topic = str(gap.get("topic") or "")
        subject_id = subject_for_gap_topic(topic)
        if not subject_id:
            continue
        entry = next((e for e in SUBJECT_CATALOG if e["id"] == subject_id), None)
        if not entry:
            continue
        slot = scan_book_slot(entry)
        if not slot.file_present:
            continue
        if slot.format == "epub" and not pandoc_available():
            log.info("Gap ingest skipped for %s: pandoc not on PATH", subject_id)
            continue
        if slot.ingested_chunks > 0:
            continue

        sid = subject_id

        def worker(job, _sid=sid):
            from backend.corpus.jobs import _append_log

            _append_log(job, f"Gap-driven ingest: {_sid}")
            return ingest_subject(_sid, chapters=None)

        start_job(f"gap_ingest_{subject_id}", worker)
        triggered.append(subject_id)
        break  # one book at a time per plan
    return triggered
