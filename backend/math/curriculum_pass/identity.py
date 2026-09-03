from __future__ import annotations

import re

from backend.math.curriculum_pass.constants import SOURCES

_SAFE = re.compile(r"[^a-zA-Z0-9._-]+")


def sanitize_source_id(raw: str) -> str:
    s = _SAFE.sub("_", (raw or "").strip())
    return s[:120] or "unknown"


def make_question_id(source: str, source_id: str) -> str:
    src = (source or "").strip().lower()
    if src not in SOURCES:
        raise ValueError(f"unknown source: {source!r}")
    return f"math.{src}.{sanitize_source_id(source_id)}"


def attach_provenance(q: dict, source: str, source_id: str) -> dict:
    out = dict(q)
    out["source"] = source
    out["source_id"] = str(source_id)
    out["id"] = make_question_id(source, str(source_id))
    return out
