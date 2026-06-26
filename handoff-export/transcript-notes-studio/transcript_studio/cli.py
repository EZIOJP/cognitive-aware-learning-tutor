"""CLI entry point for Transcript Notes Studio."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import transcript_studio  # noqa: F401 — repo root bootstrap

from transcript_studio.config import load_config
from transcript_studio.log_setup import setup_logging

setup_logging()
from transcript_studio.llm_client import llm_available
from transcript_studio.live_captions import LiveCaptionsScraper, check_captions_deps, ensure_windows
from transcript_studio.notes_generator import generate_notes_from_file, list_transcripts, parse_transcript
from transcript_studio.parse_audit import audit_parse, format_audit_report
from transcript_studio.source_loader import load_source_file


def _cmd_capture(args: argparse.Namespace) -> int:
    ok, msg = check_captions_deps()
    if not ok:
        print(f"Error: {msg}", file=sys.stderr)
        return 1
    try:
        ensure_windows()
    except OSError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    cfg = load_config()
    scraper = LiveCaptionsScraper(
        poll_interval=cfg.captions_poll_interval,
        method=cfg.captions_method,  # type: ignore[arg-type]
    )
    duration = args.duration if args.duration is not None else cfg.captions_duration_sec
    max_seconds = duration if duration and duration > 0 else None
    print("Capturing Live Captions — Ctrl+C to stop…", file=sys.stderr)
    try:
        scraper.run(max_seconds=max_seconds)
    except KeyboardInterrupt:
        pass
    out_dir = Path(args.output) if args.output else cfg.transcripts_path()
    path = scraper.save(output_dir=out_dir)
    print(f"Transcript saved: {path}")
    return 0


def _cmd_parse(args: argparse.Namespace) -> int:
    cfg = load_config()
    path = Path(args.file)
    if not path.is_file():
        path = cfg.transcripts_path() / args.file
    if not path.is_file():
        print(f"Error: not found: {args.file}", file=sys.stderr)
        return 1
    print(parse_transcript(load_source_file(path), aggressive=args.aggressive))
    if getattr(args, "audit", False):
        report = audit_parse(load_source_file(path), aggressive=args.aggressive)
        print("\n" + format_audit_report(report), file=sys.stderr)
    return 0


def _cmd_generate(args: argparse.Namespace) -> int:
    cfg = load_config()
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
            if not args.input:
                raise FileNotFoundError("--input required unless --latest")
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
            use_semantic_grouping=not args.no_semantic and not args.fast,
            use_tag_extraction=not args.no_tags and not args.fast,
            inject_wikilinks=not args.no_wikilinks,
            on_progress=lambda m: print(m, file=sys.stderr),
        )
    except (FileNotFoundError, ValueError, RuntimeError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    print(f"Notes saved: {path}")
    return 0


def _cmd_export_handoff(args: argparse.Namespace) -> int:
    studio_root = Path(__file__).resolve().parents[1]
    if str(studio_root) not in sys.path:
        sys.path.insert(0, str(studio_root))
    from export_handoff import export_bundle

    out = Path(args.output) if args.output else studio_root.parent / "handoff-export"
    return export_bundle(out.resolve(), dry_run=args.dry_run)


def _cmd_import_handoff(args: argparse.Namespace) -> int:
    studio_root = Path(__file__).resolve().parents[1]
    if str(studio_root) not in sys.path:
        sys.path.insert(0, str(studio_root))
    from export_handoff import import_bundle

    return import_bundle(Path(args.dir).resolve(), dry_run=args.dry_run)


def _legacy_generate(argv: list[str]) -> int:
    """Backward-compatible flags without subcommand."""
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
    parser.add_argument("--no-tags", action="store_true", help="Skip tag extraction pass")
    parser.add_argument("--no-wikilinks", action="store_true", help="Skip wikilink injection")
    parser.add_argument("--fast", action="store_true", help="Fast mode — chunk pass only")
    parser.add_argument("--no-semantic", action="store_true", help="Skip sentence-transformer topic grouping")
    parser.add_argument("--context", "-c", default="", help="Folder with prereq .md/.ipynb/.txt files")
    args = parser.parse_args(argv)

    if args.parse_only:
        parse_args = argparse.Namespace(file=args.parse_only, aggressive=args.aggressive)
        return _cmd_parse(parse_args)

    gen_args = argparse.Namespace(
        input=args.input,
        latest=args.latest,
        title=args.title,
        output=args.output,
        aggressive=args.aggressive,
        no_refine=args.no_refine,
        no_enrich=args.no_enrich,
        no_tags=args.no_tags,
        no_wikilinks=args.no_wikilinks,
        fast=args.fast,
        no_semantic=args.no_semantic,
        context=args.context,
    )
    return _cmd_generate(gen_args)


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0].startswith("-"):
        return _legacy_generate(argv)

    parser = argparse.ArgumentParser(description="Transcript Notes Studio — unified CLI")
    sub = parser.add_subparsers(dest="command", required=True)

    cap = sub.add_parser("capture", help="Capture Windows Live Captions to data/transcripts/")
    cap.add_argument("--duration", type=float, default=None, help="Auto-stop after N seconds (0 = until Ctrl+C)")
    cap.add_argument("--output", "-o", default="", help="Transcripts folder override")
    cap.set_defaults(func=_cmd_capture)

    gen = sub.add_parser("generate", help="Generate markdown notes from a transcript")
    src = gen.add_mutually_exclusive_group(required=True)
    src.add_argument("--input", "-i", help="Transcript path or filename in data/transcripts/")
    src.add_argument("--latest", action="store_true", help="Use newest transcript")
    gen.add_argument("--title", "-t", default="", help="Note title")
    gen.add_argument("--output", "-o", default="", help="Notes output folder")
    gen.add_argument("--aggressive", action="store_true", help="Aggressive live-caption dedup")
    gen.add_argument("--no-refine", action="store_true", help="Skip 2nd-pass refine")
    gen.add_argument("--no-enrich", action="store_true", help="Skip reference enrich pass")
    gen.add_argument("--no-tags", action="store_true", help="Skip tag extraction")
    gen.add_argument("--no-wikilinks", action="store_true", help="Skip wikilink injection")
    gen.add_argument("--fast", action="store_true", help="Fast mode")
    gen.add_argument("--no-semantic", action="store_true", help="Skip semantic chunking")
    gen.add_argument("--context", "-c", default="", help="Context folder for references")
    gen.set_defaults(func=_cmd_generate)

    parse_p = sub.add_parser("parse", help="Clean transcript and print to stdout")
    parse_p.add_argument("file", help="Transcript path or filename")
    parse_p.add_argument("--aggressive", action="store_true", help="Aggressive dedup")
    parse_p.add_argument("--audit", action="store_true", help="Print cleanup loss report to stderr")
    parse_p.set_defaults(func=_cmd_parse)

    export_p = sub.add_parser("export-handoff", help="Export portable code handoff bundle")
    export_p.add_argument("-o", "--output", default="", help="Output folder (default: ../handoff-export)")
    export_p.add_argument("--dry-run", action="store_true", help="List files only")
    export_p.set_defaults(func=_cmd_export_handoff)

    imp = sub.add_parser("import-handoff", help="Import handoff bundle back into monorepo")
    imp.add_argument("dir", help="Path to handoff-export folder")
    imp.add_argument("--dry-run", action="store_true", help="List files only")
    imp.set_defaults(func=_cmd_import_handoff)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
