"""Corpus CLI — ingest, query, verify, benchmark."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from backend.corpus.ingest import ingest_path
from backend.corpus.paths import resolve_repo_path
from backend.corpus.purge import purge_document, purge_test_documents
from backend.corpus.registry import chunk_count, list_documents, verify_document
from backend.corpus.retrieve import format_hits_for_prompt, hybrid_retrieve


def cmd_ingest(args: argparse.Namespace) -> int:
    path = resolve_repo_path(args.path)
    result = ingest_path(source=args.source, path=path, chapter=args.chapter)
    print(json.dumps(result, indent=2))
    return 0


def cmd_ingest_all_books(args: argparse.Namespace) -> int:
    from backend.corpus.library import ingest_all_full_books

    result = ingest_all_full_books(
        skip_indexed=not args.force,
        force=args.force,
        log=lambda line: print(line, flush=True),
    )
    print(json.dumps(result, indent=2))
    return 0 if result["ingested"] > 0 or result["skipped"] else 1


def cmd_build_golden(args: argparse.Namespace) -> int:
    from backend.corpus.build_golden import build_golden_fixture

    report = build_golden_fixture(
        fixture_path=resolve_repo_path(args.fixture) if args.fixture else None,
        top_k=args.top_k,
    )
    print(json.dumps(report, indent=2))
    return 0


def cmd_ingest_lecture(args: argparse.Namespace) -> int:
    from backend.corpus.handoff import ingest_lecture_handoff
    from backend.transcripts.notes_generator import resolve_transcript_path

    transcript_path = resolve_transcript_path(args.transcript)
    note_path = resolve_repo_path(args.note) if args.note else None
    result = ingest_lecture_handoff(transcript_path=transcript_path, note_path=note_path)
    print(json.dumps(result, indent=2))
    return 0


def cmd_query(args: argparse.Namespace) -> int:
    tags = [t.strip() for t in (args.subject or "").split(",") if t.strip()] or None
    hits = hybrid_retrieve(args.query, subject_tags=tags, top_k=args.top_k)
    if args.format == "prompt":
        print(format_hits_for_prompt(hits, max_chars=args.max_chars))
    else:
        print(json.dumps(hits, indent=2))
    return 0


def cmd_verify_registry(args: argparse.Namespace) -> int:
    report = verify_document(args.document)
    print(json.dumps(report, indent=2))
    return 0 if report["chunk_count"] > 0 else 1


def cmd_status(_args: argparse.Namespace) -> int:
    docs = list_documents()
    print(json.dumps({
        "documents": [
            {
                "document_id": d.document_id,
                "title": d.title,
                "chunks": chunk_count(document_id=d.document_id),
            }
            for d in docs
        ],
        "total_chunks": chunk_count(),
    }, indent=2))
    return 0


def cmd_benchmark(args: argparse.Namespace) -> int:
    from backend.corpus.benchmark import run_benchmark

    golden_path = resolve_repo_path(args.golden)
    report = run_benchmark(golden_path, top_k=args.top_k)
    print(json.dumps(report, indent=2))
    return 0


def cmd_purge_document(args: argparse.Namespace) -> int:
    result = purge_document(args.document)
    print(json.dumps(result, indent=2))
    return 0


def cmd_purge_test(_args: argparse.Namespace) -> int:
    result = purge_test_documents()
    print(json.dumps(result, indent=2))
    return 0 if result["purged"] >= 0 else 1


def cmd_health(_args: argparse.Namespace) -> int:
    from backend.corpus.health import get_corpus_health

    report = get_corpus_health()
    print(json.dumps(report, indent=2))
    return 0 if report.get("healthy") else 1


def cmd_seed_equations(args: argparse.Namespace) -> int:
    from backend.corpus.converters import file_to_markdown, find_source_file, load_metadata
    from backend.corpus.kg_anchor import extract_equation_nodes, seed_mml_concepts
    from backend.corpus.library import _subject_folder
    from backend.db.base import SessionLocal

    folder = _subject_folder("linear_algebra")
    meta = load_metadata(folder)
    src = find_source_file(folder, meta)
    if src is None:
        print("Error: MML source file not found in raw_library/linear_algebra", file=sys.stderr)
        return 1
    document_id = meta.get("document_id") or "mml_2021_deisenroth"
    chapters = args.chapters or [1, 2]
    db = SessionLocal()
    created_total = 0
    try:
        seed_mml_concepts(db, user_id=None, chapters=chapters, document_id=document_id)
        for ch in chapters:
            md = file_to_markdown(src, chapter=ch)
            created_total += len(
                extract_equation_nodes(
                    db,
                    user_id=None,
                    chapter=ch,
                    markdown=md,
                    document_id=document_id,
                )
            )
    finally:
        db.close()
    print(json.dumps({"chapters": chapters, "equation_nodes_created": created_total}, indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="backend.corpus.cli", description="Local corpus ingest and retrieval")
    sub = p.add_subparsers(dest="command", required=True)

    ing = sub.add_parser("ingest", help="Ingest transcript, note, or textbook folder")
    ing.add_argument("--source", required=True, choices=["transcript", "note", "textbook"])
    ing.add_argument("--path", required=True, help="File or folder path")
    ing.add_argument("--chapter", type=int, default=None, help="Textbook chapter number")
    ing.set_defaults(func=cmd_ingest)

    ing_all = sub.add_parser("ingest-all-books", help="Ingest full PDF/EPUB books in raw_library")
    ing_all.add_argument(
        "--force",
        action="store_true",
        help="Re-ingest even when chunks already exist",
    )
    ing_all.set_defaults(func=cmd_ingest_all_books)

    ing_lec = sub.add_parser("ingest-lecture", help="Ingest transcript + note into corpus")
    ing_lec.add_argument("--transcript", required=True, help="Transcript filename or path")
    ing_lec.add_argument("--note", default="", help="Note relative path under data/notes")
    ing_lec.set_defaults(func=cmd_ingest_lecture)

    bg = sub.add_parser("build-golden", help="Refresh mml_golden_qa.json from live retrieval")
    bg.add_argument("--fixture", default="tests/fixtures/mml_golden_qa.json")
    bg.add_argument("--top-k", type=int, default=5)
    bg.set_defaults(func=cmd_build_golden)

    q = sub.add_parser("query", help="Hybrid retrieve")
    q.add_argument("query", help="Search query")
    q.add_argument("--subject", default="", help="Comma-separated subject tags")
    q.add_argument("--top-k", type=int, default=5)
    q.add_argument("--format", choices=["json", "prompt"], default="json")
    q.add_argument("--max-chars", type=int, default=12000)
    q.set_defaults(func=cmd_query)

    v = sub.add_parser("verify-registry", help="Verify document chunks in registry")
    v.add_argument("--document", required=True)
    v.set_defaults(func=cmd_verify_registry)

    sub.add_parser("status", help="Corpus status").set_defaults(func=cmd_status)

    b = sub.add_parser("benchmark", help="Run golden-set retrieval benchmark")
    b.add_argument("--golden", default="tests/fixtures/mml_golden_qa.json")
    b.add_argument("--top-k", type=int, default=5)
    b.set_defaults(func=cmd_benchmark)

    pd = sub.add_parser("purge-document", help="Remove a document and rebuild indexes")
    pd.add_argument("--document", required=True)
    pd.set_defaults(func=cmd_purge_document)

    sub.add_parser("purge-test", help="Remove test_* documents from production registry").set_defaults(
        func=cmd_purge_test
    )

    sub.add_parser("health", help="Corpus health and known issues").set_defaults(func=cmd_health)

    se = sub.add_parser("seed-equations", help="Post-hoc LLM equation nodes for MML chapters")
    se.add_argument("--chapters", type=int, nargs="+", default=[1, 2])
    se.set_defaults(func=cmd_seed_equations)

    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.func(args))
    except Exception as exc:  # noqa: BLE001
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
