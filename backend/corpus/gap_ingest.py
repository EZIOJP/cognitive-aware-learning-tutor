"""Gap-ingest stubs — corpus library removed."""

from __future__ import annotations

from typing import Any


def subject_for_gap_topic(topic: str) -> str | None:
    return None


def pandoc_available() -> bool:
    return False


def trigger_gap_ingest_for_gaps(gaps: list[dict[str, Any]]) -> list[str]:
    return []
