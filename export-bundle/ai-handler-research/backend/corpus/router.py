"""HTTP API for corpus library setup and ingest."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.config import get_settings
from backend.core.auth import get_current_user
from backend.db.session import get_db
from backend.corpus.jobs import get_job, job_to_dict, start_job
from backend.corpus.handoff import ingest_lecture_handoff
from backend.corpus.library import (
    get_corpus_overview,
    ingest_all_full_books,
    ingest_latest_transcripts,
    ingest_subject,
    read_setup_log_tail,
    run_auto_setup,
    save_upload,
)
from backend.models import User

router = APIRouter(prefix="/api/corpus", tags=["corpus"])


class IngestBookRequest(BaseModel):
    subject_id: str = Field(..., min_length=1, max_length=64)
    chapters: list[int] | None = None


class RunSetupRequest(BaseModel):
    mml_chapters: list[int] = Field(default_factory=lambda: [1, 2])
    transcript_limit: int = Field(default=3, ge=0, le=20)
    ingest_full_books: bool = True
    skip_indexed_books: bool = True
    test_query: bool = True


class IngestAllBooksRequest(BaseModel):
    skip_indexed: bool = True
    force: bool = False


class GroundedNotesRequest(BaseModel):
    transcript_file: str = Field(..., min_length=1, max_length=200)
    topic: str = Field(default="", max_length=160)
    title: str = Field(default="", max_length=200)
    folder_path: str = Field(default="", max_length=300)


class IngestLectureRequest(BaseModel):
    transcript_file: str = Field(..., min_length=1, max_length=200)
    note_path: str = Field(default="", max_length=400)


@router.get("/overview")
def corpus_overview(_user: User = Depends(get_current_user)):
    """Books on disk, ingest status, and transcript list."""
    return get_corpus_overview()


@router.get("/log")
def corpus_log(lines: int = 80, _user: User = Depends(get_current_user)):
    return {"log": read_setup_log_tail(lines=min(lines, 200))}


@router.get("/job")
def corpus_job(job_id: str | None = None, _user: User = Depends(get_current_user)):
    job = get_job(job_id)
    if job is None:
        return {"job": None}
    return {"job": job_to_dict(job)}


@router.post("/run-setup")
def corpus_run_setup(body: RunSetupRequest, _user: User = Depends(get_current_user)):
    """One-click: metadata + MML chapters + latest transcripts + verify."""
    existing = get_job()
    if existing and existing.status == "running":
        raise HTTPException(status_code=409, detail="A setup job is already running")

    def worker(job):
        return run_auto_setup(
            job,
            mml_chapters=body.mml_chapters,
            transcript_limit=body.transcript_limit,
            ingest_full_books=body.ingest_full_books,
            skip_indexed_books=body.skip_indexed_books,
            test_query=body.test_query,
        )

    job = start_job("auto_setup", worker)
    return {"job": job_to_dict(job)}


@router.post("/ingest-book")
def corpus_ingest_book(body: IngestBookRequest, _user: User = Depends(get_current_user)):
    existing = get_job()
    if existing and existing.status == "running":
        raise HTTPException(status_code=409, detail="A corpus job is already running")

    subject_id = body.subject_id
    chapters = body.chapters

    def worker(job):
        from backend.corpus.jobs import _append_log

        label = f"chapters {chapters}" if chapters else "full book"
        _append_log(job, f"Ingesting {subject_id} ({label})")
        try:
            return ingest_subject(subject_id, chapters=chapters)
        except FileNotFoundError as exc:
            raise ValueError(str(exc)) from exc

    job = start_job(f"ingest_{subject_id}", worker)
    return {"job": job_to_dict(job)}


@router.post("/ingest-all-books")
def corpus_ingest_all_books(body: IngestAllBooksRequest, _user: User = Depends(get_current_user)):
    """Background ingest of every full-book PDF/EPUB slot on disk."""
    existing = get_job()
    if existing and existing.status == "running":
        raise HTTPException(status_code=409, detail="A corpus job is already running")

    def worker(job):
        from backend.corpus.jobs import _append_log

        def log(line: str) -> None:
            _append_log(job, line)

        _append_log(job, "Full-book ingest started")
        return ingest_all_full_books(skip_indexed=body.skip_indexed, force=body.force, log=log)

    job = start_job("ingest_all_books", worker)
    return {"job": job_to_dict(job)}


@router.post("/ingest-transcripts")
def corpus_ingest_transcripts(limit: int = 3, _user: User = Depends(get_current_user)):
    return ingest_latest_transcripts(limit=min(limit, 20))


@router.post("/upload/{subject_id}")
async def corpus_upload_book(
    subject_id: str,
    file: UploadFile = File(...),
    _user: User = Depends(get_current_user),
):
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="Empty file")
    try:
        return save_upload(subject_id, file.filename or "book.bin", data)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/generate-notes-grounded")
def corpus_generate_notes_grounded(
    body: GroundedNotesRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    settings = get_settings()
    if not settings.corpus_grounded_notes:
        from backend.transcripts.notes_generator import generate_notes_from_file, resolve_transcript_path

        path = resolve_transcript_path(body.transcript_file)
        notes_path, content = generate_notes_from_file(
            path,
            title=body.title.strip() or body.topic.strip() or None,
            folder_path=body.folder_path.strip(),
        )
        handoff = ingest_lecture_handoff(transcript_path=path, note_path=notes_path)
        from backend.paths import NOTES_DIR
        from backend.transcripts.router import _save_generated_note

        rel = notes_path.relative_to(NOTES_DIR).as_posix()
        _save_generated_note(
            db,
            user,
            notes_path,
            content,
            title=body.title.strip() or path.stem,
            topic=body.topic.strip() or None,
            source="live_captions",
            transcript_file=body.transcript_file,
            folder_path=body.folder_path.strip(),
        )
        return {
            "mode": "legacy_flag_off",
            "filename": rel,
            "notes_path": str(notes_path),
            "markdown": content,
            "corpus_handoff": handoff,
        }
    from backend.corpus.grounded_notes import generate_grounded_notes
    from backend.core.ollama_client import get_llm_config, LlmOptions
    from backend.paths import NOTES_DIR
    from backend.transcripts.router import _save_generated_note

    cfg = get_llm_config()
    llm = LlmOptions(provider=cfg["provider"], base_url=cfg["base_url"], model=cfg["model"])
    result = generate_grounded_notes(
        transcript_file=body.transcript_file,
        topic=body.topic,
        title=body.title.strip() or None,
        folder_path=body.folder_path.strip(),
        llm=llm,
        ingest_corpus=True,
    )
    notes_path = Path(result.get("notes_path") or "")
    if notes_path.is_file():
        rel = notes_path.relative_to(NOTES_DIR).as_posix()
        _save_generated_note(
            db,
            user,
            notes_path,
            result.get("markdown") or notes_path.read_text(encoding="utf-8"),
            title=body.title.strip() or body.transcript_file,
            topic=body.topic.strip() or None,
            source="grounded_corpus",
            transcript_file=body.transcript_file,
            folder_path=body.folder_path.strip(),
        )
        result["filename"] = rel
    return result


@router.post("/ingest-lecture")
def corpus_ingest_lecture(body: IngestLectureRequest, _user: User = Depends(get_current_user)):
    from backend.transcripts.notes_generator import resolve_transcript_path

    transcript_path = resolve_transcript_path(body.transcript_file)
    note_path = Path(body.note_path.strip()) if body.note_path.strip() else None
    try:
        return ingest_lecture_handoff(transcript_path=transcript_path, note_path=note_path)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
