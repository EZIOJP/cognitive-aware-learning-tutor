"""Bible reader API — offline WEB verses, chapter goal, bookmarks, day pass."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.bible import store as bible_store
from backend.bible import structured as bible_text
from backend.bible.paths import ensure_bible_pdf
from backend.core.auth import get_current_user
from backend.db.session import get_db
from backend.models import User

router = APIRouter(prefix="/api/bible", tags=["bible"])


class HeartbeatIn(BaseModel):
    page: int = Field(1, ge=1)
    focused: bool = True


class ChapterHeartbeatIn(BaseModel):
    book: str = Field(..., min_length=1)
    chapter: int = Field(1, ge=1)
    verse: int = Field(1, ge=1)
    focused: bool = True


class ChapterTickIn(BaseModel):
    book: str = Field(..., min_length=1)
    chapter: int = Field(1, ge=1)
    done: bool = True


class BookmarkIn(BaseModel):
    page: int = Field(1, ge=1)
    label: str = ""


class DayPassIn(BaseModel):
    confirm: str = Field("", description="Type PASS to spend a weekly day pass")


class RewardDayIn(BaseModel):
    confirm: str = Field("", description="Type REWARD to spend an earned reward day")


@router.get("/pdf")
def get_pdf(user: User = Depends(get_current_user)):
    """Optional legacy GNB PDF — not required for chapter goal."""
    try:
        path = ensure_bible_pdf()
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return FileResponse(
        path,
        media_type="application/pdf",
        filename="good-news-bible.pdf",
        headers={"Cache-Control": "private, max-age=3600"},
    )


@router.get("/v2/meta")
def v2_meta(version: str = "web", user: User = Depends(get_current_user)):
    try:
        return bible_text.meta(version)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/v2/today")
def v2_today(
    version: str = "web",
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Today's single assigned chapter + verses (no book/chapter browser)."""
    assigned = bible_store.resolve_today_chapter(user.id, version=version)
    try:
        chapter = bible_text.read_chapter(version, assigned["book"], int(assigned["chapter"]))
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except (KeyError, IndexError) as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    from backend.behavior.distraction_gate import compute_distraction_gate

    base = bible_store.summary(user.id)
    gate = compute_distraction_gate(db, user.id)
    return {
        **base,
        "today_chapter": assigned,
        "chapter": chapter,
        "preview_verses": (chapter.get("verses") or [])[:3],
        "gate": gate,
        "bookmarks": bible_store.list_bookmarks(user.id),
    }


@router.get("/v2/read/{version}/{book}/{chapter}")
def v2_read(
    version: str,
    book: str,
    chapter: int,
    user: User = Depends(get_current_user),
):
    """Read a chapter — morning UI should prefer /v2/today; this stays for data access."""
    try:
        return bible_text.read_chapter(version, book, chapter)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except IndexError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/v2/heartbeat")
def v2_heartbeat(body: ChapterHeartbeatIn, user: User = Depends(get_current_user)):
    """Optional reading-minutes credit only — does not mark the chapter done."""
    return bible_store.apply_chapter_heartbeat(
        user.id,
        book=body.book,
        chapter=body.chapter,
        focused=body.focused,
        verse=body.verse,
    )


@router.post("/v2/chapters/tick")
def v2_tick_chapter(body: ChapterTickIn, user: User = Depends(get_current_user)):
    try:
        return bible_store.tick_chapter(
            user.id, book=body.book, chapter=body.chapter, done=body.done
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/state")
def get_state(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    from backend.behavior.distraction_gate import compute_distraction_gate

    base = bible_store.summary(user.id)
    gate = compute_distraction_gate(db, user.id)
    return {**base, "gate": gate, "bookmarks": bible_store.list_bookmarks(user.id)}


@router.get("/day-pass")
def get_day_pass(user: User = Depends(get_current_user)):
    return bible_store.day_pass_status(user.id)


@router.post("/day-pass")
def post_day_pass(
    body: DayPassIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    """Spend one weekly pass — unlocks games until midnight without Bible reading."""
    try:
        out = bible_store.request_day_pass(user.id, confirm=body.confirm)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    from backend.behavior.distraction_gate import compute_distraction_gate

    out["gate"] = compute_distraction_gate(db, user.id)
    return out


@router.get("/reward-day")
def get_reward_day(user: User = Depends(get_current_user)):
    from backend.behavior.reward_days import status

    return status(user.id)


@router.post("/reward-day")
def post_reward_day(
    body: RewardDayIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    """Spend a credit earned from four completed focus-and-Bible days."""
    from backend.behavior.distraction_gate import compute_distraction_gate
    from backend.behavior.reward_days import claim_reward_day

    gate = compute_distraction_gate(db, user.id)
    try:
        out = claim_reward_day(
            user.id,
            confirm=body.confirm,
            already_unlocked=bool(gate.get("day_unlimited")),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    out["gate"] = compute_distraction_gate(db, user.id)
    return out


@router.post("/heartbeat")
def heartbeat(body: HeartbeatIn, user: User = Depends(get_current_user)):
    return bible_store.apply_heartbeat(user.id, page=body.page, focused=body.focused)


@router.get("/bookmarks")
def bookmarks(user: User = Depends(get_current_user)):
    return {"bookmarks": bible_store.list_bookmarks(user.id)}


@router.post("/bookmarks")
def create_bookmark(body: BookmarkIn, user: User = Depends(get_current_user)):
    return bible_store.add_bookmark(user.id, body.page, body.label)


@router.delete("/bookmarks/{bookmark_id}")
def remove_bookmark(bookmark_id: int, user: User = Depends(get_current_user)):
    if not bible_store.delete_bookmark(user.id, bookmark_id):
        raise HTTPException(status_code=404, detail="Bookmark not found")
    return {"ok": True}
