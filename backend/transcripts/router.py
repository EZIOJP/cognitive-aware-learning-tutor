"""API routes for transcript capture and lecture notes."""

from __future__ import annotations

import logging
import time
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.core.auth import get_current_user
from backend.core.ollama_client import LlmOptions, get_llm_config, llm_reachable, resolve_llm_options
from backend.db.session import get_db
from backend.models import User
from backend.paths import TRANSCRIPTS_DIR
from backend.transcripts.kb import list_note_records, list_topics, row_to_item, save_note_record
from backend.transcripts.library import (
    build_library_tree,
    create_folder,
    create_note_file,
    delete_folder,
    delete_note,
    list_notes_in_folder,
    move_note,
    sync_disk_notes_for_user,
    save_note_content,
    update_note_meta,
    update_reading_state,
)
from backend.transcripts.notes_generator import (
    generate_notes_from_file,
    list_transcripts,
    resolve_notes_path,
    resolve_transcript_path,
)
from backend.transcripts.sources import resolve_source_path
from backend.transcripts.snapshots import (
    append_snapshot_marker,
    next_snapshot_index,
    resolve_snapshot_path,
    save_snapshot_png,
)
from backend.hub.services.knowledge_graph import index_note_file
from backend.transcripts.block_regenerate import regenerate_block, regenerate_selection
from backend.transcripts.note_block_repair import repair_all_blocks
from backend.transcripts.study_intel import (
    drills_to_markdown,
    gap_summary_markdown,
    generate_code_drills,
    generate_quiz_items,
    load_note_text,
    quiz_to_markdown,
    run_gap_analysis,
    summarize_folder,
    sync_session_items,
)

router = APIRouter(prefix="/api/transcripts", tags=["transcripts"])
log = logging.getLogger(__name__)


class GenerateNotesRequest(BaseModel):
    transcript_file: str = Field(..., min_length=1, max_length=200)
    reference_paths: list[str] = Field(default_factory=list, max_length=8)
    context_folder: str = Field(default="", max_length=512)
    title: str = Field(default="", max_length=120)
    topic: str = Field(default="", max_length=160)
    folder_path: str = Field(default="", max_length=512)
    aggressive_dedup: bool = False
    use_semantic_grouping: bool = True
    refine_second_pass: bool = False
    enrich_with_references: bool = True
    use_tag_extraction: bool = False
    fast_mode: bool = False
    llm_provider: str | None = Field(default=None, max_length=32)
    llm_base_url: str | None = Field(default=None, max_length=200)
    llm_model: str | None = Field(default=None, max_length=120)


class GenerateTodayRequest(BaseModel):
    title: str = Field(default="", max_length=120)
    topic: str = Field(default="", max_length=160)
    folder_path: str = Field(default="", max_length=512)
    aggressive_dedup: bool = False
    use_semantic_grouping: bool = True
    refine_second_pass: bool = False
    enrich_with_references: bool = True
    use_tag_extraction: bool = False
    fast_mode: bool = False
    llm_provider: str | None = Field(default=None, max_length=32)
    llm_base_url: str | None = Field(default=None, max_length=200)
    llm_model: str | None = Field(default=None, max_length=120)


class CreateFolderRequest(BaseModel):
    folder_path: str = Field(..., min_length=1, max_length=512)


class CreateFileRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=120)
    folder_path: str = Field(default="", max_length=512)
    kind: str = Field(default="note", max_length=32)
    topic: str | None = Field(default=None, max_length=160)


class UpdateFileRequest(BaseModel):
    dest_folder: str | None = Field(default=None, max_length=512)
    new_title: str | None = Field(default=None, max_length=120)
    kind: str | None = Field(default=None, max_length=32)
    title: str | None = Field(default=None, max_length=120)
    topic: str | None = Field(default=None, max_length=160)


class SaveNoteContentRequest(BaseModel):
    content: str = Field(default="", max_length=500_000)


class ReadingStateRequest(BaseModel):
    read_scroll_top: int | None = Field(default=None, ge=0)
    bookmark_scroll_top: int | None = Field(default=None, ge=0)
    set_bookmark_from_read: bool = False


class FolderSummarizeRequest(BaseModel):
    folder_path: str = Field(..., min_length=0, max_length=512)
    title: str | None = Field(default=None, max_length=120)
    llm_provider: str | None = Field(default=None, max_length=32)
    llm_base_url: str | None = Field(default=None, max_length=200)
    llm_model: str | None = Field(default=None, max_length=120)


class GapAnalysisRequest(BaseModel):
    lecture_path: str = Field(..., min_length=1, max_length=512)
    reference_path: str = Field(..., min_length=1, max_length=512)
    llm_provider: str | None = Field(default=None, max_length=32)
    llm_base_url: str | None = Field(default=None, max_length=200)
    llm_model: str | None = Field(default=None, max_length=120)


class GenerateIntelRequest(BaseModel):
    source_paths: list[str] = Field(default_factory=list, max_length=4)
    topic: str = Field(default="", max_length=160)
    count: int = Field(default=5, ge=1, le=10)
    folder_path: str = Field(default="", max_length=512)
    llm_provider: str | None = Field(default=None, max_length=32)
    llm_base_url: str | None = Field(default=None, max_length=200)
    llm_model: str | None = Field(default=None, max_length=120)


class SyncSessionItem(BaseModel):
    id: str = Field(..., min_length=1, max_length=64)
    kind: str = Field(default="quiz", max_length=32)
    title: str = Field(..., min_length=1, max_length=120)
    content: str = Field(..., min_length=1)
    approved: bool = True
    topic: str | None = Field(default=None, max_length=160)


class SyncSessionRequest(BaseModel):
    folder_path: str = Field(default="", max_length=512)
    items: list[SyncSessionItem] = Field(default_factory=list)


class RegenerateBlockRequest(BaseModel):
    block_type: str = Field(..., pattern="^(mermaid|code)$")
    language: str = Field(default="python", max_length=32)
    content: str = Field(default="", max_length=50_000)
    error: str | None = Field(default=None, max_length=2000)
    instruction: str | None = Field(default=None, max_length=500)
    mode: str = Field(default="fix", pattern="^(fix|polish)$")
    note_context: str | None = Field(default=None, max_length=8000)
    llm_provider: str | None = Field(default=None, max_length=32)
    llm_base_url: str | None = Field(default=None, max_length=200)
    llm_model: str | None = Field(default=None, max_length=120)


class RegenerateBlockResponse(BaseModel):
    content: str
    block_type: str
    language: str


class RegenerateSelectionRequest(BaseModel):
    selection: str = Field(..., min_length=1, max_length=50_000)
    note_context: str | None = Field(default=None, max_length=8000)
    instruction: str | None = Field(default=None, max_length=500)
    llm_provider: str | None = Field(default=None, max_length=32)
    llm_base_url: str | None = Field(default=None, max_length=200)
    llm_model: str | None = Field(default=None, max_length=120)


class RegenerateSelectionResponse(BaseModel):
    content: str


class RepairAllBlocksRequest(BaseModel):
    content: str = Field(..., min_length=1, max_length=500_000)
    use_llm: bool = True
    llm_provider: str | None = Field(default=None, max_length=32)
    llm_base_url: str | None = Field(default=None, max_length=200)
    llm_model: str | None = Field(default=None, max_length=120)


class RepairBlockDetail(BaseModel):
    index: int
    lang: str
    method: str
    status: str


class RepairAllBlocksResponse(BaseModel):
    content: str
    fixed_count: int
    details: list[RepairBlockDetail]


class RepairAndSaveRequest(BaseModel):
    use_llm: bool = True
    llm_provider: str | None = Field(default=None, max_length=32)
    llm_base_url: str | None = Field(default=None, max_length=200)
    llm_model: str | None = Field(default=None, max_length=120)


def _llm_from_intel(body: GapAnalysisRequest | GenerateIntelRequest) -> LlmOptions | None:
    if not any([body.llm_provider, body.llm_base_url, body.llm_model]):
        return None
    return LlmOptions(
        provider=body.llm_provider,
        base_url=body.llm_base_url,
        model=body.llm_model,
    )


class GenerateNotesResponse(BaseModel):
    filename: str
    path: str
    preview: str
    topic: str | None = None
    source: str = "live_captions"


def _llm_from_request(body: GenerateNotesRequest | GenerateTodayRequest) -> LlmOptions | None:
    if not any([body.llm_provider, body.llm_base_url, body.llm_model]):
        return None
    return LlmOptions(
        provider=body.llm_provider,
        base_url=body.llm_base_url,
        model=body.llm_model,
    )


@router.get("/llm-config")
def get_llm_settings(
    llm_provider: str | None = None,
    llm_base_url: str | None = None,
    llm_model: str | None = None,
    _user: User = Depends(get_current_user),
):
    cfg = get_llm_config()
    if any([llm_provider, llm_base_url, llm_model]):
        override = LlmOptions(
            provider=llm_provider or cfg["provider"],
            base_url=llm_base_url or cfg["base_url"],
            model=llm_model or cfg["model"],
        )
    else:
        override = LlmOptions(
            provider=cfg["provider"],
            base_url=cfg["base_url"],
            model=cfg["model"],
        )
    return {
        **cfg,
        "provider": override.provider,
        "base_url": override.base_url,
        "model": override.model,
        "reachable": llm_reachable(override),
    }


def _llm_from_regenerate(body: RegenerateBlockRequest) -> LlmOptions | None:
    if not any([body.llm_provider, body.llm_base_url, body.llm_model]):
        return None
    return LlmOptions(
        provider=body.llm_provider,
        base_url=body.llm_base_url,
        model=body.llm_model,
    )


@router.post("/library/regenerate-block", response_model=RegenerateBlockResponse)
def regenerate_note_block(body: RegenerateBlockRequest, _user: User = Depends(get_current_user)):
    llm = _llm_from_regenerate(body)
    opts = resolve_llm_options(llm)
    log.info(
        "regenerate-block type=%s mode=%s provider=%s model=%s base=%s",
        body.block_type,
        body.mode,
        opts.provider,
        opts.model,
        opts.base_url,
    )
    try:
        fixed = regenerate_block(
            block_type=body.block_type,
            language=body.language,
            content=body.content,
            error=body.error,
            instruction=body.instruction,
            note_context=body.note_context,
            mode=body.mode,
            llm=_llm_from_regenerate(body),
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return RegenerateBlockResponse(
        content=fixed,
        block_type=body.block_type,
        language=body.language,
    )


@router.post("/library/regenerate-selection", response_model=RegenerateSelectionResponse)
def regenerate_note_selection(body: RegenerateSelectionRequest, _user: User = Depends(get_current_user)):
    try:
        fixed = regenerate_selection(
            selection=body.selection,
            note_context=body.note_context,
            instruction=body.instruction,
            llm=_llm_from_regenerate(body),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return RegenerateSelectionResponse(content=fixed)


@router.post("/library/repair-all-blocks", response_model=RepairAllBlocksResponse)
def repair_note_all_blocks(body: RepairAllBlocksRequest, _user: User = Depends(get_current_user)):
    try:
        fixed, details = repair_all_blocks(
            body.content,
            llm=_llm_from_regenerate(body),
            use_llm=body.use_llm,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return RepairAllBlocksResponse(
        content=fixed,
        fixed_count=len(details),
        details=[RepairBlockDetail(**d) for d in details],
    )


def _read_note_file(relative_path: str) -> tuple[str, str]:
    """Return (relative_path posix, file content)."""
    from backend.paths import NOTES_DIR

    try:
        path = resolve_notes_path(relative_path)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Note not found.")
    rel = path.relative_to(NOTES_DIR).as_posix()
    return rel, path.read_text(encoding="utf-8")


def _llm_from_repair_save(body: RepairAndSaveRequest) -> LlmOptions | None:
    if not any([body.llm_provider, body.llm_base_url, body.llm_model]):
        return None
    return LlmOptions(
        provider=body.llm_provider,
        base_url=body.llm_base_url,
        model=body.llm_model,
    )


@router.post("/library/files/{relative_path:path}/repair-all-blocks", response_model=RepairAllBlocksResponse)
def repair_and_save_library_note(
    relative_path: str,
    body: RepairAndSaveRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Read note from disk, repair all blocks, save atomically."""
    rel, raw = _read_note_file(relative_path)
    try:
        fixed, details = repair_all_blocks(
            raw,
            llm=_llm_from_repair_save(body),
            use_llm=body.use_llm,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    try:
        save_note_content(db, user_id=user.id, relative_path=rel, content=fixed)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return RepairAllBlocksResponse(
        content=fixed,
        fixed_count=len(details),
        details=[RepairBlockDetail(**d) for d in details],
    )


def _today_live_caption_files() -> list[Path]:
    today = datetime.now(timezone.utc).strftime("%Y%m%d")
    TRANSCRIPTS_DIR.mkdir(parents=True, exist_ok=True)
    matches = [
        p
        for p in TRANSCRIPTS_DIR.glob("live_captions_*.txt")
        if today in p.name
    ]
    return sorted(matches, key=lambda p: p.stat().st_mtime, reverse=True)


def _save_generated_note(
    db: Session,
    user: User,
    path: Path,
    content: str,
    *,
    title: str,
    topic: str | None,
    source: str,
    transcript_file: str | None,
    folder_path: str = "",
) -> None:
    from backend.paths import NOTES_DIR

    rel = path.relative_to(NOTES_DIR).as_posix()
    save_note_record(
        db,
        user_id=user.id,
        filename=rel,
        relative_path=rel,
        folder_path=folder_path,
        kind="lecture",
        title=title,
        topic=topic,
        source=source,
        transcript_file=transcript_file,
        content=content,
    )


@router.get("")
def get_transcripts(_user: User = Depends(get_current_user)):
    return {"items": list_transcripts()}


@router.get("/notes")
def get_notes_list(
    topic: str | None = None,
    search: str | None = None,
    folder_path: str | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    rows = list_note_records(db, user.id, topic=topic, search=search, folder_path=folder_path)
    return {"items": [row_to_item(r) for r in rows]}


@router.get("/notes/topics")
def get_note_topics(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    topics = list_topics(db, user.id)
    return {"topics": topics}


@router.get("/library/tree")
def get_library_tree(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    sync_disk_notes_for_user(db, user.id)
    return build_library_tree(db, user.id)


@router.post("/library/folders")
def post_library_folder(body: CreateFolderRequest, _user: User = Depends(get_current_user)):
    try:
        path = create_folder(body.folder_path)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"folder_path": path}


@router.post("/library/files")
def post_library_file(
    body: CreateFileRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    try:
        row = create_note_file(
            db,
            user_id=user.id,
            title=body.title,
            folder_path=body.folder_path,
            kind=body.kind,
            topic=body.topic,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return row_to_item(row)


@router.patch("/library/files/{relative_path:path}/reading")
def patch_library_reading_state(
    relative_path: str,
    body: ReadingStateRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    try:
        state = update_reading_state(
            db,
            user_id=user.id,
            relative_path=relative_path,
            read_scroll_top=body.read_scroll_top,
            bookmark_scroll_top=body.bookmark_scroll_top,
            set_bookmark_from_read=body.set_bookmark_from_read,
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return state


@router.patch("/library/files/{relative_path:path}")
def patch_library_file(
    relative_path: str,
    body: UpdateFileRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    try:
        if body.dest_folder is not None or body.new_title:
            row = move_note(
                db,
                user_id=user.id,
                relative_path=relative_path,
                dest_folder=body.dest_folder or "",
                new_title=body.new_title,
            )
        else:
            row = update_note_meta(
                db,
                user_id=user.id,
                relative_path=relative_path,
                kind=body.kind,
                title=body.title,
                topic=body.topic,
            )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return row_to_item(row)


@router.put("/library/files/{relative_path:path}/content")
def put_library_file_content(
    relative_path: str,
    body: SaveNoteContentRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    try:
        row = save_note_content(
            db,
            user_id=user.id,
            relative_path=relative_path,
            content=body.content,
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {
        "relative_path": (row.relative_path or row.filename or "").replace("\\", "/"),
        "content": body.content,
        "section_count": row.section_count,
    }


@router.delete("/library/files/{relative_path:path}")
def delete_library_file(
    relative_path: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    try:
        delete_note(db, user_id=user.id, relative_path=relative_path)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"deleted": True, "relative_path": relative_path.replace("\\", "/")}


@router.delete("/library/folders/{folder_path:path}")
def delete_library_folder(
    folder_path: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    try:
        removed = delete_folder(db, user_id=user.id, folder_path=folder_path)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"deleted": True, "folder_path": folder_path.replace("\\", "/"), "notes_removed": removed}


@router.post("/library/folders/summarize")
def post_folder_summarize(
    body: FolderSummarizeRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    llm = get_llm_config(
        provider=body.llm_provider,
        base_url=body.llm_base_url,
        model=body.llm_model,
    )
    try:
        result = summarize_folder(
            db,
            user_id=user.id,
            folder_path=body.folder_path,
            llm=llm,
            title=body.title,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return result


@router.get("/library/files/{relative_path:path}/content")
def get_library_file_content(relative_path: str, _user: User = Depends(get_current_user)):
    rel, content = _read_note_file(relative_path)
    return {"filename": rel, "relative_path": rel, "content": content}


@router.get("/notes/content/{relative_path:path}")
def get_note_content(relative_path: str, _user: User = Depends(get_current_user)):
    rel, content = _read_note_file(relative_path)
    return {"filename": rel, "relative_path": rel, "content": content}


def _note_title_for_export(db: Session, user_id: int, rel: str, path: Path) -> str:
    from backend.transcripts.library import _find_note_row

    row = _find_note_row(db, user_id, rel)
    if row and row.title:
        return row.title
    return path.stem.replace("_", " ").strip() or "Lecture Notes"


@router.get("/library/files/{relative_path:path}/export")
def export_library_file(
    relative_path: str,
    format: str = Query(..., pattern="^(pdf|docx)$"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Download a single note as PDF or Word (.docx) with embedded images."""
    import io

    from backend.paths import NOTES_DIR
    from backend.transcripts.note_export import export_note

    try:
        path = resolve_notes_path(relative_path)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Note not found.")
    rel = path.relative_to(NOTES_DIR).as_posix()
    content = path.read_text(encoding="utf-8")
    title = _note_title_for_export(db, user.id, rel, path)
    try:
        data, media_type, filename = export_note(
            content, title=title, note_relative=rel, fmt=format  # type: ignore[arg-type]
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return StreamingResponse(
        io.BytesIO(data),
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/library/folders/export")
def export_library_folder_root(
    format: str = Query(..., pattern="^(pdf|docx)$"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Export all notes at library root."""
    return export_library_folder("", format=format, db=db, user=user)


@router.get("/library/folders/{folder_path:path}/export")
def export_library_folder(
    folder_path: str,
    format: str = Query(..., pattern="^(pdf|docx)$"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Download all notes in a folder (recursive) as one PDF or Word file."""
    import io

    from backend.paths import NOTES_DIR
    from backend.transcripts.note_export import combine_folder_notes, export_note

    rels = list_notes_in_folder(folder_path, recursive=True)
    if not rels:
        raise HTTPException(status_code=404, detail="No notes in this folder.")

    bundle: list[tuple[str, str, str]] = []
    for rel in rels:
        path = (NOTES_DIR / rel).resolve()
        if not path.is_file() or not path.is_relative_to(NOTES_DIR.resolve()):
            continue
        title = _note_title_for_export(db, user.id, rel, path)
        bundle.append((rel, title, path.read_text(encoding="utf-8")))

    if not bundle:
        raise HTTPException(status_code=404, detail="No readable notes in this folder.")

    combined, folder_title = combine_folder_notes(bundle)
    anchor = bundle[0][0]
    try:
        data, media_type, filename = export_note(
            combined,
            title=folder_title,
            note_relative=anchor,
            fmt=format,  # type: ignore[arg-type]
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    safe_folder = folder_title.replace(" ", "_")[:40] or "folder"
    ext = "pdf" if format == "pdf" else "docx"
    return StreamingResponse(
        io.BytesIO(data),
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{safe_folder}_notes.{ext}"'},
    )


def _load_sources(db: Session, user_id: int, paths: list[str]) -> list[str]:
    texts: list[str] = []
    for p in paths:
        p = p.strip()
        if not p:
            continue
        try:
            texts.append(load_note_text(db, user_id, p))
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
    return texts


@router.post("/library/gap-analysis")
def post_gap_analysis(
    body: GapAnalysisRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    try:
        lecture = load_note_text(db, user.id, body.lecture_path)
        reference = load_note_text(db, user.id, body.reference_path)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    result = run_gap_analysis(lecture, reference, llm=_llm_from_intel(body))
    summary_md = gap_summary_markdown(
        result,
        lecture_title=body.lecture_path.split("/")[-1],
        reference_title=body.reference_path.split("/")[-1],
    )
    return {**result, "summary_markdown": summary_md}


@router.post("/library/generate-quiz")
def post_generate_quiz(
    body: GenerateIntelRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if not body.source_paths:
        raise HTTPException(status_code=400, detail="source_paths required")
    texts = _load_sources(db, user.id, body.source_paths)
    result = generate_quiz_items(
        texts,
        count=body.count,
        topic=body.topic.strip(),
        llm=_llm_from_intel(body),
    )
    title = body.topic.strip() or "Generated Quiz"
    md = quiz_to_markdown(result["questions"], title=title)
    return {
        **result,
        "markdown": md,
        "session_item": {
            "id": f"quiz-{int(time.time())}",
            "kind": "quiz",
            "title": title,
            "content": md,
            "detail": f"{len(result['questions'])} questions",
        },
    }


@router.post("/library/generate-drills")
def post_generate_drills(
    body: GenerateIntelRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if not body.source_paths:
        raise HTTPException(status_code=400, detail="source_paths required")
    texts = _load_sources(db, user.id, body.source_paths)
    result = generate_code_drills(
        texts,
        count=min(body.count, 5),
        topic=body.topic.strip(),
        llm=_llm_from_intel(body),
    )
    title = body.topic.strip() or "Code Drills"
    md = drills_to_markdown(result["drills"], title=title)
    return {
        **result,
        "markdown": md,
        "session_item": {
            "id": f"drill-{int(time.time())}",
            "kind": "exercise",
            "title": title,
            "content": md,
            "detail": f"{len(result['drills'])} exercises",
        },
    }


@router.post("/library/sync-session")
def post_sync_session(
    body: SyncSessionRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    items = [item.model_dump() for item in body.items]
    if not any(i.get("approved") for i in items):
        raise HTTPException(status_code=400, detail="No approved items to save.")
    saved = sync_session_items(
        db,
        user_id=user.id,
        folder_path=body.folder_path.strip(),
        items=items,
    )
    return {"saved": saved, "count": len(saved)}


@router.post("/notes/generate", response_model=GenerateNotesResponse)
def generate_notes(
    body: GenerateNotesRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    try:
        transcript_path = resolve_transcript_path(body.transcript_file)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not transcript_path.is_file():
        raise HTTPException(status_code=404, detail="Transcript not found.")
    title = body.title.strip() or transcript_path.stem
    topic = body.topic.strip() or None
    folder = body.folder_path.strip()
    reference_paths: list[Path] = []
    for rel in body.reference_paths:
        try:
            reference_paths.append(resolve_source_path(rel.strip()))
        except (ValueError, FileNotFoundError) as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
    context_folder = body.context_folder.strip() or None
    try:
        path, content = generate_notes_from_file(
            transcript_path,
            title=title,
            aggressive=body.aggressive_dedup,
            llm=_llm_from_request(body),
            folder_path=folder,
            reference_paths=reference_paths or None,
            context_folder=context_folder,
            use_semantic_grouping=body.use_semantic_grouping,
            refine_second_pass=body.refine_second_pass,
            enrich_with_references=body.enrich_with_references,
            use_tag_extraction=body.use_tag_extraction,
            fast_mode=body.fast_mode,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    _save_generated_note(
        db,
        user,
        path,
        content,
        title=title,
        topic=topic,
        source="live_captions",
        transcript_file=body.transcript_file,
        folder_path=folder,
    )
    from backend.paths import NOTES_DIR

    rel = path.relative_to(NOTES_DIR).as_posix()
    return GenerateNotesResponse(
        filename=rel,
        path=str(path),
        preview=content[:500],
        topic=topic,
        source="live_captions",
    )


@router.post("/notes/generate-today", response_model=GenerateNotesResponse)
def generate_notes_from_today(
    body: GenerateTodayRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    files = _today_live_caption_files()
    if not files:
        raise HTTPException(status_code=404, detail="No live_captions transcript captured today.")
    transcript_path = files[0]
    title = body.title.strip() or transcript_path.stem.replace("_", " ")
    topic = body.topic.strip() or title
    folder = body.folder_path.strip()
    try:
        path, content = generate_notes_from_file(
            transcript_path,
            title=title,
            aggressive=body.aggressive_dedup,
            llm=_llm_from_request(body),
            folder_path=folder,
            use_semantic_grouping=body.use_semantic_grouping,
            refine_second_pass=body.refine_second_pass,
            enrich_with_references=body.enrich_with_references,
            use_tag_extraction=body.use_tag_extraction,
            fast_mode=body.fast_mode,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    _save_generated_note(
        db,
        user,
        path,
        content,
        title=title,
        topic=topic,
        source="live_captions",
        transcript_file=transcript_path.name,
        folder_path=folder,
    )
    from backend.paths import NOTES_DIR

    rel = path.relative_to(NOTES_DIR).as_posix()
    return GenerateNotesResponse(
        filename=rel,
        path=str(path),
        preview=content[:500],
        topic=topic,
        source="live_captions",
    )


@router.post("/snapshots")
async def upload_snapshot(
    transcript_file: str = Form(...),
    image: UploadFile = File(...),
    _user: User = Depends(get_current_user),
):
    try:
        transcript_path = resolve_transcript_path(transcript_file)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not transcript_path.parent.exists():
        TRANSCRIPTS_DIR.mkdir(parents=True, exist_ok=True)
    if not transcript_path.is_file():
        transcript_path.touch()

    index = next_snapshot_index(transcript_path)
    data = await image.read()
    if not data:
        raise HTTPException(status_code=400, detail="Empty image.")
    save_snapshot_png(transcript_file, index, data)
    marker = append_snapshot_marker(transcript_path, index)
    return {"index": index, "marker": marker}


@router.get("/snapshots/{stem}/{index}.png")
def get_snapshot(stem: str, index: int, _user: User = Depends(get_current_user)):
    try:
        path = resolve_snapshot_path(stem, index)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Snapshot not found.")
    return FileResponse(path, media_type="image/png")


class QuizAnswerRequest(BaseModel):
    note_path: str = Field(..., description="Note file that the quiz was generated from.")
    topic: str = Field(..., description="Topic or heading the question is about.")
    is_correct: bool
    score: float = Field(default=1.0, ge=0.0, le=1.0)


@router.post("/quiz-answer")
def submit_quiz_answer(
    body: QuizAnswerRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Log a quiz answer as a knowledge graph observation."""
    from backend.hub.services.knowledge_graph import log_observation, upsert_node  # noqa: PLC0415
    from pathlib import Path  # noqa: PLC0415

    note_path = Path(body.note_path)
    try:
        kg_node = upsert_node(
            db,
            user_id=current_user.id,
            label=body.topic,
            node_type="concept",
            note_path=str(note_path),
        )
        log_observation(
            db,
            node_id=kg_node.id,
            user_id=current_user.id,
            interaction_type="quiz_pass" if body.is_correct else "quiz_fail",
            value=body.score,
        )
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    return {"logged": True, "topic": body.topic, "correct": body.is_correct}


class IndexNoteRequest(BaseModel):
    note_path: str = Field(..., description="Relative or absolute path to the markdown note file.")


class IndexNoteResponse(BaseModel):
    indexed_nodes: int
    note_path: str


@router.post("/index-note", response_model=IndexNoteResponse)
def index_note_endpoint(
    req: IndexNoteRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Parse a markdown note and upsert knowledge graph nodes for every ## heading."""
    path = Path(req.note_path)
    if not path.is_absolute():
        from backend.paths import NOTES_DIR  # noqa: PLC0415

        path = NOTES_DIR / path
    if not path.is_file():
        raise HTTPException(status_code=404, detail=f"Note not found: {req.note_path}")
    nodes = index_note_file(db, path, user_id=current_user.id)
    return IndexNoteResponse(indexed_nodes=len(nodes), note_path=str(path))
