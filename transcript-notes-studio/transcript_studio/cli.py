"""CLI entry point for transcript notes generation."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from transcript_studio.config import load_config
from transcript_studio.llm_client import llm_available
from transcript_studio.notes_generator import generate_notes_from_file, list_transcripts, parse_transcript
from transcript_studio.source_loader import load_source_file


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Transcript Notes Studio — CLI")
    src = parser.add_mutually_exclusive_group(required=True)
    src.add_argument("--input", "-i", help="Source .txt / .md / .pdf path or filename in data/transcripts/")
    src.add_argument("--latest", action="store_true", help="Use newest .txt in transcripts folder")
    src.add_argument("--parse-only", metavar="FILE", help="Only clean transcript and print to stdout")
    parser.add_argument("--title", "-t", default="", help="Note title")
    parser.add_argument("--output", "-o", default="", help="Output folder for .md notes")
    parser.add_argument("--aggressive", action="store_true", help="Aggressive live-caption dedup")
    parser.add_argument("--no-refine", action="store_true", help="Skip 2nd-pass topic stitching")
    parser.add_argument("--no-enrich", action="store_true", help="Skip 3rd-pass enrich with references")
    parser.add_argument("--fast", action="store_true", help="Fast mode — chunk pass only (skip refine and enrich)")
    parser.add_argument("--context", "-c", default="", help="Folder with prereq .md/.ipynb/.txt files")
    args = parser.parse_args(argv)

    cfg = load_config()

    if args.parse_only:
        path = Path(args.parse_only)
        if not path.is_file():
            path = cfg.transcripts_path() / args.parse_only
        if not path.is_file():
            print(f"Error: not found: {args.parse_only}", file=sys.stderr)
            return 1
        print(parse_transcript(load_source_file(path), aggressive=args.aggressive))
        return 0

    if not llm_available(cfg):
        print("Error: LLM not enabled. Edit config.json or set LLM_ENABLED=1 in .env", file=sys.stderr)
        return 1

    try:
        if args.latest:
            files = list_transcripts()
            if not files:
                raise FileNotFoundError(f"No .txt in {cfg.transcripts_path()}")
            transcript_path = files[0]
        else:
            transcript_path = Path(args.input)
            if not transcript_path.is_file():
                transcript_path = cfg.transcripts_path() / args.input
            if not transcript_path.is_file():
                raise FileNotFoundError(args.input)

        out_dir = Path(args.output) if args.output else None
        title = args.title.strip() or transcript_path.stem.replace("_", " ")
        path, _ = generate_notes_from_file(
            transcript_path,
            title=title,
            aggressive=args.aggressive,
            output_dir=out_dir,
            context_folder=args.context or None,
            refine_second_pass=not args.no_refine and not args.fast,
            enrich_with_references=not args.no_enrich and not args.fast,
            fast_mode=args.fast,
            on_progress=lambda m: print(m, file=sys.stderr),
        )
    except (FileNotFoundError, ValueError, RuntimeError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    print(f"Notes saved: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
