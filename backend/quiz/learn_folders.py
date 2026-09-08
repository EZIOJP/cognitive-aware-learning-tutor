"""Learn hierarchy folders under ``data/notes/`` (Math Core first)."""

from __future__ import annotations

from typing import Any

# Display / sort order — Math Core pinned first.
LEARN_FOLDER_ORDER: tuple[str, ...] = (
    "math-core",
    "math",
    "numpy",
    "pandas",
    "lecture",
    "vocab",
)

LEARN_FOLDER_LABELS: dict[str, str] = {
    "math-core": "Math Core",
    "math": "Math",
    "numpy": "NumPy",
    "pandas": "Pandas",
    "lecture": "Lecture",
    "vocab": "Vocab",
}

# MT0 fluency + MT1 Math Core companion tags → math-core even if path missing.
_MATH_CORE_TAGS = frozenset(
    {
        "MT1-T01",
        "MT0-T01",
        "MT0-T02",
        "MT0-T03",
        "MT0-T04",
        "MT0-T05",
        "MT0-T06",
        "MT0-T07",
        "MT0-T08",
        "MT0-T09",
        # legacy worksheet ids
        "MT1-T16",
        "MT1-T17",
        "MT1-T18",
        "MT1-T19",
        "MT1-T20",
        "MT1-T21",
        "MT1-T22",
        "MT1-T23",
        "MT1-T24",
    }
)


def folder_rank(folder: str) -> int:
    try:
        return LEARN_FOLDER_ORDER.index(folder)
    except ValueError:
        return len(LEARN_FOLDER_ORDER) + 1


def folder_from_note_path(rel: str) -> str | None:
    rel = (rel or "").replace("\\", "/").lstrip("/")
    if not rel or rel.startswith("rules/"):
        return None
    top = rel.split("/", 1)[0]
    if top in LEARN_FOLDER_LABELS:
        return top
    # Flat legacy basename heuristics
    name = rel.rsplit("/", 1)[-1].lower()
    if name.startswith("mt1_") or "aptitude_interview" in name:
        return "math-core"
    if name.startswith("mt"):
        return "math"
    if "numpy" in name or name.startswith("l02_") or name.startswith("l03_"):
        return "numpy"
    if "pandas" in name or name.startswith("l04_") or name.startswith("l05_"):
        return "pandas"
    if name.startswith("l") and "_notes" in name:
        return "lecture"
    return None


def folder_for_tag(tag_id: str, note_paths: list[str] | None = None) -> str:
    tid = (tag_id or "").strip().upper()
    paths = list(note_paths or [])

    for p in paths:
        f = folder_from_note_path(p)
        if f:
            return f

    if tid in _MATH_CORE_TAGS or tid.startswith("MT0-") or tid.startswith("MT1-"):
        return "math-core"
    if tid.startswith("MT"):
        return "math"
    if tid.startswith("VOCAB") or tid.startswith("VOCAB.GROUP") or tid.lower().startswith("vocab."):
        return "vocab"
    # L2/L3 → numpy, L4/L5 → pandas, other L* → lecture
    if tid.startswith("L"):
        import re

        m = re.match(r"^L(\d+)-T", tid, re.IGNORECASE)
        if m:
            n = int(m.group(1))
            if n in (2, 3):
                return "numpy"
            if n in (4, 5):
                return "pandas"
        return "lecture"
    if tid.lower().startswith("vocab."):
        return "vocab"
    return "other"


def enrich_tag_folder(entry: dict[str, Any]) -> dict[str, Any]:
    tid = str(entry.get("id") or "")
    paths = list(entry.get("note_paths") or [])
    folder = folder_for_tag(tid, paths)
    entry["folder"] = folder
    entry["folder_label"] = LEARN_FOLDER_LABELS.get(folder, folder.replace("-", " ").title())
    entry["folder_rank"] = folder_rank(folder) if folder != "other" else 99
    # Keep legacy ``group`` soft buckets for filters
    if folder == "math-core" or folder == "math":
        entry["group"] = "math"
    elif folder in ("numpy", "pandas", "lecture"):
        entry["group"] = "lecture"
    elif folder == "vocab":
        entry["group"] = "vocab"
    else:
        entry.setdefault("group", "other")
    return entry
