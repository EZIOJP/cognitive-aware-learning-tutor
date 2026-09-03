from __future__ import annotations

import re

_TOPIC_RE = re.compile(r"^(L|MT)\s*(\d+)\s*[-_]\s*T\s*(\d+)$", re.IGNORECASE)


def canonicalize_topic_id(raw: str) -> str | None:
    """Normalize ``mt1-t7`` / ``MT1-T07`` → ``MT1-T07`` (local copy for curriculum_pass)."""
    text = (raw or "").strip().strip("`")
    m = _TOPIC_RE.fullmatch(text)
    if not m:
        return None
    kind = m.group(1).upper()
    if kind == "MT":
        kind = "MT"
    else:
        kind = "L"
    return f"{kind}{int(m.group(2))}-T{int(m.group(3)):02d}"
