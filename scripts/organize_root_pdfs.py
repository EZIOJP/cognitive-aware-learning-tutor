"""Copy PDFs from project root into data/raw_library/ with canonical names."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw_library"
ARCHIVE = RAW / "_archive" / "root_imports"

SLOTS: list[tuple[str, str, str]] = [
    ("Mathematics For Machine Learning", "linear_algebra", "Mathematics_for_ML.pdf"),
    ("Data Science from Scratch", "foundations", "Data_Science_from_Scratch.pdf"),
    ("Practical statistics", "statistics", "Practical_Statistics.pdf"),
    ("Designing machine learning systems", "ml_systems", "Designing_ML_Systems.pdf"),
    ("Artificial intelligence", "ai_context", "AI_Guide_Thinking_Humans.pdf"),
]

METADATA_PDF_UPDATES: dict[str, dict[str, str]] = {
    "foundations": {"format": "pdf", "filename": "Data_Science_from_Scratch.pdf"},
    "statistics": {"format": "pdf", "filename": "Practical_Statistics.pdf"},
    "ai_context": {"format": "pdf", "filename": "AI_Guide_Thinking_Humans.pdf"},
}


def _match_root_pdf(prefix: str) -> Path | None:
    prefix_l = prefix.lower()
    for path in sorted(ROOT.glob("*.pdf")):
        if path.name.lower().startswith(prefix_l):
            return path
    return None


def main() -> int:
    ARCHIVE.mkdir(parents=True, exist_ok=True)
    copied: list[str] = []

    for prefix, subject_id, dest_name in SLOTS:
        src = _match_root_pdf(prefix)
        if src is None:
            dest = RAW / subject_id / dest_name
            if dest.is_file():
                copied.append(f"SKIP (already in library): {subject_id}/{dest_name}")
            else:
                copied.append(f"MISSING: no root PDF matching {prefix!r}")
            continue

        folder = RAW / subject_id
        folder.mkdir(parents=True, exist_ok=True)
        dest = folder / dest_name
        shutil.copy2(src, dest)
        shutil.move(str(src), str(ARCHIVE / src.name))
        copied.append(f"OK {subject_id}/{dest_name} <- {src.name[:60]}...")

    for subject_id, updates in METADATA_PDF_UPDATES.items():
        meta_path = RAW / subject_id / "metadata.json"
        if not meta_path.is_file():
            continue
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        meta.update(updates)
        meta_path.write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
        copied.append(f"META {subject_id}: format=pdf")

    # Move legacy EPUBs aside so only PDF is used
    for subject_id in ("foundations", "statistics", "ai_context"):
        folder = RAW / subject_id
        epub_archive = folder / "_archive"
        epub_archive.mkdir(exist_ok=True)
        for epub in folder.glob("*.epub"):
            shutil.move(str(epub), str(epub_archive / epub.name))
            copied.append(f"ARCHIVED epub: {subject_id}/{epub.name}")

    print("\n".join(copied))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
