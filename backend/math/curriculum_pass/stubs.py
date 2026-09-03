from __future__ import annotations

import re
from pathlib import Path

from backend.math.curriculum_pass.constants import MODULE_NOTE_FILES
from backend.math.curriculum_pass.topic_ids import canonicalize_topic_id
from backend.quiz.atomic_io import atomic_write_text

_HEADING_RE = re.compile(
    r"^##\s+`?(MT\d+-T\d+)`?\s*(?:—|-|–|:)\s*(.+)$",
    re.IGNORECASE | re.MULTILINE,
)


def _module_id(mt: str) -> str:
    m = re.match(r"(MT\d+)", mt, re.IGNORECASE)
    if not m:
        raise ValueError(f"not an MT module id: {mt!r}")
    return m.group(1).upper().replace("MT", "MT")  # keep MTn


def _normalize_module(mt: str) -> str:
    m = re.match(r"(MT)(\d+)", mt, re.IGNORECASE)
    if not m:
        raise ValueError(f"not an MT module id: {mt!r}")
    return f"MT{int(m.group(2))}"


def ensure_note_stubs(
    mt_rows: list[tuple[str, str]],
    *,
    notes_dir: Path,
) -> dict[str, int]:
    stubs_created = 0
    stubs_skipped_nonempty = 0
    notes_dir.mkdir(parents=True, exist_ok=True)

    # Group by module file
    by_file: dict[str, list[tuple[str, str]]] = {}
    for mt, title in mt_rows:
        canon = canonicalize_topic_id(mt) or mt
        mod = _normalize_module(canon)
        fname = MODULE_NOTE_FILES.get(mod)
        if not fname:
            # Unknown module — skip rather than invent filename from title
            continue
        by_file.setdefault(fname, []).append((canon, title))

    for fname, rows in by_file.items():
        path = notes_dir / fname
        text = path.read_text(encoding="utf-8") if path.is_file() else ""
        existing: dict[str, str] = {}
        for m in _HEADING_RE.finditer(text):
            tid = canonicalize_topic_id(m.group(1)) or m.group(1)
            existing[tid] = m.group(0)

        # Split into sections for body emptiness check
        parts = re.split(r"(?m)^(##\s+.+)$", text)
        bodies: dict[str, str] = {}
        i = 1
        while i + 1 < len(parts):
            heading = parts[i].strip()
            body = (parts[i + 1] or "").strip()
            hm = _HEADING_RE.match(heading)
            if hm:
                tid = canonicalize_topic_id(hm.group(1)) or hm.group(1)
                bodies[tid] = body
            i += 2

        additions: list[str] = []
        for mt, title in rows:
            if mt in existing:
                body = bodies.get(mt, "")
                if body and body != "TODO: fill notes":
                    stubs_skipped_nonempty += 1
                continue
            block = f"## `{mt}` — {title}\n\nTODO: fill notes\n"
            additions.append(block)
            stubs_created += 1

        if additions:
            new_text = text.rstrip() + ("\n\n" if text.strip() else "") + "\n\n".join(additions)
            if not new_text.endswith("\n"):
                new_text += "\n"
            atomic_write_text(path, new_text)

    return {
        "stubs_created": stubs_created,
        "stubs_skipped_nonempty": stubs_skipped_nonempty,
    }
