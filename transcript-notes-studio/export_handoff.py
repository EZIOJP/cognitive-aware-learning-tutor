#!/usr/bin/env python3
"""Export or import a portable Transcript Notes Studio handoff bundle.

Usage (from transcript-notes-studio/):
  python export_handoff.py
  python export_handoff.py -o ../handoff-export
  python export_handoff.py --import ../handoff-export --dry-run
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

STUDIO_ROOT = Path(__file__).resolve().parent
REPO_ROOT = STUDIO_ROOT.parent
MANIFEST_PATH = STUDIO_ROOT / "handoff" / "FLOW_MANIFEST.json"
DEFAULT_OUT = REPO_ROOT / "handoff-export"


def _load_manifest() -> dict:
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def _should_exclude(rel_posix: str, exclude_globs: list[str]) -> bool:
    from fnmatch import fnmatch

    return any(fnmatch(rel_posix, pat) for pat in exclude_globs)


def _copy_file(src: Path, dst: Path, *, dry_run: bool) -> None:
    if dry_run:
        print(f"  copy {src.relative_to(REPO_ROOT)}")
        return
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)


def _copy_tree_filtered(
    src_dir: Path,
    dst_dir: Path,
    *,
    root_label: str,
    exclude_globs: list[str],
    dry_run: bool,
) -> int:
    count = 0
    if not src_dir.is_dir():
        return 0
    for path in sorted(src_dir.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(src_dir).as_posix()
        prefixed = f"{root_label}/{rel}" if root_label else rel
        if _should_exclude(prefixed, exclude_globs):
            continue
        if path.name.endswith(".pyc"):
            continue
        _copy_file(path, dst_dir / rel, dry_run=dry_run)
        count += 1
    return count


def export_bundle(out_dir: Path, *, dry_run: bool = False) -> int:
    manifest = _load_manifest()
    copy_sets = manifest["copy_sets"]
    studio_cfg = copy_sets["studio"]
    exclude = studio_cfg.get("exclude_globs", [])

    if not dry_run:
        if out_dir.exists():
            shutil.rmtree(out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)

    print(f"Exporting to {out_dir}")
    total = 0

    # Studio tree
    studio_dst = out_dir / "transcript-notes-studio"
    total += _copy_tree_filtered(
        STUDIO_ROOT,
        studio_dst,
        root_label="transcript-notes-studio",
        exclude_globs=exclude,
        dry_run=dry_run,
    )

    # Explicit backend / docs / scripts / tests files
    for key in ("backend_notes_engine", "backend_tests", "docs", "scripts"):
        for rel in copy_sets[key]["files"]:
            src = REPO_ROOT / rel.replace("/", "\\") if sys.platform == "win32" else REPO_ROOT / rel
            rel_path = Path(rel)
            dst = out_dir / rel_path
            if not src.is_file():
                print(f"  skip missing: {rel}", file=sys.stderr)
                continue
            _copy_file(src, dst, dry_run=dry_run)
            total += 1

    # Handoff readme + manifest at bundle root
    for name in ("README.md", "FLOW_MANIFEST.json"):
        src = STUDIO_ROOT / "handoff" / name
        _copy_file(src, out_dir / name, dry_run=dry_run)
        total += 1

    # Main handoff doc at bundle root
    handoff_doc = REPO_ROOT / "docs" / "TRANSCRIPT_STUDIO_HANDOFF.md"
    if handoff_doc.is_file():
        _copy_file(handoff_doc, out_dir / "TRANSCRIPT_STUDIO_HANDOFF.md", dry_run=dry_run)
        total += 1

    # Empty data dirs
    for sub in ("data/transcripts", "data/notes"):
        marker = out_dir / sub / ".gitkeep"
        if not dry_run:
            marker.parent.mkdir(parents=True, exist_ok=True)
            if not marker.is_file():
                marker.write_text("", encoding="utf-8")
        total += 1

    # Write export metadata
    meta = {
        "exported_from": str(REPO_ROOT),
        "manifest_version": manifest.get("version"),
        "file_count_approx": total,
    }
    if not dry_run:
        (out_dir / "EXPORT_META.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")

    print(f"Done — {total} paths ({'dry-run' if dry_run else 'written'})")
    return 0


def import_bundle(src_dir: Path, *, dry_run: bool = False) -> int:
    if not src_dir.is_dir():
        print(f"Not a directory: {src_dir}", file=sys.stderr)
        return 1

    manifest_file = src_dir / "FLOW_MANIFEST.json"
    if not manifest_file.is_file():
        print("FLOW_MANIFEST.json missing — not a valid handoff bundle", file=sys.stderr)
        return 1

    manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
    copy_sets = manifest["copy_sets"]
    print(f"Importing from {src_dir} -> {REPO_ROOT} ({'dry-run' if dry_run else 'apply'})")

    studio_src = src_dir / "transcript-notes-studio"
    if studio_src.is_dir():
        studio_dst = REPO_ROOT / "transcript-notes-studio"
        for path in sorted(studio_src.rglob("*")):
            if not path.is_file():
                continue
            rel = path.relative_to(studio_src)
            if "handoff-export" in rel.parts:
                continue
            dst = studio_dst / rel
            _copy_file(path, dst, dry_run=dry_run)

    for key in ("backend_notes_engine", "backend_tests", "docs", "scripts"):
        for rel in copy_sets[key]["files"]:
            src = src_dir / Path(rel)
            dst = REPO_ROOT / Path(rel)
            if not src.is_file():
                print(f"  skip missing in bundle: {rel}", file=sys.stderr)
                continue
            _copy_file(src, dst, dry_run=dry_run)

    handoff_doc = src_dir / "TRANSCRIPT_STUDIO_HANDOFF.md"
    if handoff_doc.is_file():
        _copy_file(handoff_doc, REPO_ROOT / "docs" / "TRANSCRIPT_STUDIO_HANDOFF.md", dry_run=dry_run)

    print("Import complete.")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Export/import Transcript Notes Studio handoff bundle")
    parser.add_argument("-o", "--output", type=Path, default=DEFAULT_OUT, help="Export destination")
    parser.add_argument("--import", dest="import_dir", type=Path, metavar="DIR", help="Import bundle into repo")
    parser.add_argument("--dry-run", action="store_true", help="List actions only")
    args = parser.parse_args(argv)

    if args.import_dir:
        return import_bundle(args.import_dir.resolve(), dry_run=args.dry_run)
    return export_bundle(args.output.resolve(), dry_run=args.dry_run)


if __name__ == "__main__":
    raise SystemExit(main())
