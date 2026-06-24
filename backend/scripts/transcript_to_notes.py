"""CLI: turn a live-caption transcript into markdown lecture notes.

Primary entry point (Windows):
  scripts\\run_transcript_to_notes.bat --latest
  scripts\\run_transcript_to_notes.bat --input live_captions_YYYYMMDD_HHMMSS.txt

Requires OLLAMA_ENABLED=1 in .env and LM Studio / Ollama running locally.
Install embeddings once: scripts\\install_notes.bat
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from backend.config import get_settings
from backend.core.ollama_client import get_llm_config, llm_reachable, resolve_llm_options
from backend.db.base import SessionLocal
from backend.models import User
from backend.paths import NOTES_DIR, TRANSCRIPTS_DIR
from backend.transcripts.kb import save_note_record
from backend.transcripts.notes_generator import generate_notes_from_file
from backend.transcripts.sources import resolve_source_path


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate markdown lecture notes from a live-caption transcript.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m backend.scripts.transcript_to_notes --latest
  python -m backend.scripts.transcript_to_notes --latest --full --refine
  python -m backend.scripts.transcript_to_notes -i live_captions_20260623_204143.txt -f "lecture one"
        """.strip(),
    )
    src = parser.add_mutually_exclusive_group(required=True)
    src.add_argument("--input", "-i", help="Transcript path or filename in data/transcripts/")
    src.add_argument(
        "--latest",
        action="store_true",
        help="Use the newest live_captions_*.txt in data/transcripts/",
    )
    parser.add_argument("--title", "-t", default="", help="Note title (default: transcript stem)")
    parser.add_argument("--topic", default="", help="Knowledge-base topic tag (default: title)")
    parser.add_argument(
        "--folder",
        "-f",
        default="",
        help="Subfolder under data/notes/ for the output file",
    )
    parser.add_argument(
        "--context",
        "-c",
        default="",
        help="Folder of prereq .md/.txt/.ipynb to weave into notes (library path or absolute)",
    )
    parser.add_argument(
        "--reference",
        "-r",
        action="append",
        default=[],
        metavar="PATH",
        help="Reference file (.md, .pdf, .txt) — repeat for multiple",
    )
    parser.add_argument(
        "--aggressive-dedup",
        action="store_true",
        help="Salvage mode for noisy live-caption dumps",
    )
    parser.add_argument(
        "--full",
        action="store_true",
        help="Slower quality mode: semantic grouping (capped at 12 LLM calls). Default is --fast.",
    )
    parser.add_argument(
        "--fast",
        action="store_true",
        help="Quick draft: large word chunks, no embeddings (default unless --full)",
    )
    parser.add_argument(
        "--no-semantic",
        action="store_true",
        help="Word-chunk only (no sentence-transformer grouping)",
    )
    parser.add_argument(
        "--refine",
        action="store_true",
        help="Second LLM pass to polish merged notes",
    )
    parser.add_argument(
        "--no-enrich",
        action="store_true",
        help="Do not slice reference material per chunk",
    )
    parser.add_argument(
        "--tags",
        action="store_true",
        help="Extract TOPICS tags per section (extra LLM calls)",
    )
    parser.add_argument(
        "--user",
        type=str,
        default="admin",
        help="Username to index notes under (default: admin)",
    )
    return parser.parse_args()


def _resolve_input(path_str: str) -> Path:
    p = Path(path_str)
    if p.is_file():
        return p.resolve()
    candidate = TRANSCRIPTS_DIR / path_str
    if candidate.is_file():
        return candidate.resolve()
    raise FileNotFoundError(f"Transcript not found: {path_str}")


def _resolve_latest() -> Path:
    TRANSCRIPTS_DIR.mkdir(parents=True, exist_ok=True)
    files = sorted(
        TRANSCRIPTS_DIR.glob("live_captions_*.txt"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    if not files:
        raise FileNotFoundError("No live_captions_*.txt files in data/transcripts/")
    return files[0].resolve()


def _resolve_references(paths: list[str]) -> list[Path]:
    out: list[Path] = []
    for raw in paths:
        raw = raw.strip()
        if not raw:
            continue
        p = Path(raw)
        if p.is_file():
            out.append(p.resolve())
            continue
        try:
            out.append(resolve_source_path(raw).resolve())
        except (FileNotFoundError, ValueError) as exc:
            raise FileNotFoundError(f"Reference not found: {raw}") from exc
    return out


def _configure_stdio() -> None:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:
            try:
                reconfigure(encoding="utf-8", errors="replace")
            except (OSError, ValueError):
                pass


def _progress(msg: str) -> None:
    print(msg, file=sys.stderr, flush=True)


def _index_in_kb(
    *,
    note_path: Path,
    content: str,
    title: str,
    topic: str | None,
    transcript_file: str,
    folder_path: str,
    username: str,
) -> None:
    rel = note_path.relative_to(NOTES_DIR).as_posix()
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.username == username).first()
        if not user:
            _progress(f"Note: user {username!r} not found — skipped library index (file still saved on disk).")
            return
        save_note_record(
            db,
            user_id=user.id,
            filename=rel,
            relative_path=rel,
            folder_path=folder_path,
            kind="lecture",
            title=title,
            topic=topic,
            source="live_captions",
            transcript_file=transcript_file,
            content=content,
        )
        _progress(f"Indexed in study library: {rel}")
    finally:
        db.close()


def _check_llm() -> None:
    if not get_settings().ollama_enabled:
        raise RuntimeError(
            "Local LLM is not enabled. Set OLLAMA_ENABLED=1 in .env, "
            "then start Ollama or LM Studio with your model loaded."
        )
    cfg = get_llm_config()
    if not llm_reachable():
        raise RuntimeError(
            f"LLM not reachable at {cfg.get('base_url')} "
            f"(provider={cfg.get('provider')}, model={cfg.get('model')}). "
            "Start LM Studio/Ollama and load the model, then retry."
        )
    _progress(f"LLM OK — {cfg.get('provider')} @ {cfg.get('base_url')} · {cfg.get('model')}")


def main() -> None:
    _configure_stdio()
    args = _parse_args()
    try:
        _check_llm()
        transcript_path = _resolve_latest() if args.latest else _resolve_input(args.input)
        title = args.title.strip() or transcript_path.stem.replace("_", " ")
        topic = args.topic.strip() or title
        folder = args.folder.strip()
        references = _resolve_references(args.reference)

        # Default: fast (few LLM calls). Use --full for semantic grouping.
        fast = not args.full or args.fast
        use_semantic = args.full and not args.no_semantic and not args.fast

        _progress(f"Transcript: {transcript_path.name}")
        if references:
            _progress(f"References: {', '.join(p.name for p in references)}")
        if args.context.strip():
            _progress(f"Context folder: {args.context.strip()}")
        mode_label = (
            "fast (default)" if fast and not args.full else "full/semantic" if use_semantic else "word-chunks"
        )
        chunk_cap = "max 8 LLM chunks" if fast else "max 12 LLM chunks"
        _progress(
            f"Mode: {mode_label}" + (" + refine" if args.refine else "") + f" — {chunk_cap}"
        )

        path, content = generate_notes_from_file(
            transcript_path,
            title=title,
            aggressive=args.aggressive_dedup or "live_captions" in transcript_path.name.lower(),
            llm=resolve_llm_options(),
            folder_path=folder,
            reference_paths=references or None,
            context_folder=args.context.strip() or None,
            on_progress=_progress,
            use_semantic_grouping=use_semantic,
            fast_mode=fast,
            refine_second_pass=args.refine and not fast,
            enrich_with_references=not args.no_enrich,
            use_tag_extraction=args.tags,
        )
        _index_in_kb(
            note_path=path,
            content=content,
            title=title,
            topic=topic,
            transcript_file=transcript_path.name,
            folder_path=folder,
            username=args.user,
        )
    except (FileNotFoundError, ValueError, RuntimeError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)

    rel = path.relative_to(NOTES_DIR).as_posix()
    print(f"Notes saved: {path}")
    print(f"Library path: {rel}")
    print(f"Topic: {topic}")
    print(f"Source transcript: {transcript_path.name}")
    print("Open Study Library -> Lecture Notes to read, quiz, and review.")


if __name__ == "__main__":
    main()
