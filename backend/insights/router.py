from datetime import date

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.core.auth import get_current_user
from backend.db.session import get_db
from backend.hub.services.rollup import rebuild_daily_rollup
from backend.models import LifeDailyLog, User

router = APIRouter(prefix="/api/insights", tags=["insights"])


class ReviewOut(BaseModel):
    comments: str
    next_steps: list[str]
    goals: list[str]
    overall_performance: str
    source: str = "template"


class ChatMessageIn(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    messages: list[ChatMessageIn]


class ChatResponse(BaseModel):
    reply: str
    source: str = "template"
    llm_available: bool = False


@router.get("/daily")
def insights_daily(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    d = date.today()
    life = db.query(LifeDailyLog).filter(LifeDailyLog.user_id == user.id, LifeDailyLog.date == d).first()
    rollup = rebuild_daily_rollup(db, user.id, d)

    performance = "needs-improvement"
    if life and life.life_score >= 80:
        performance = "excellent"
    elif life and life.life_score >= 55:
        performance = "good"

    return {
        "date": d.isoformat(),
        "life_score": life.life_score if life else 0,
        "study_minutes": life.study_minutes if life else 0,
        "productive_minutes": rollup.productive_minutes,
        "sleep_minutes": rollup.sleep_minutes,
        "vocab_events": rollup.vocab_events,
        "math_attempts": rollup.math_attempts,
        "overall_performance": performance,
    }


def _template_review(data: dict) -> ReviewOut:
    perf = data["overall_performance"]
    comments = {
        "excellent": "Strong day — keep your current rhythm.",
        "good": "Solid progress; small tweaks to sleep or focus could help.",
        "needs-improvement": "Take a breath — shorten sessions and protect sleep tonight.",
    }[perf]
    steps = []
    if data["sleep_minutes"] < 420:
        steps.append("Aim for 7+ hours of sleep tonight.")
    if data["productive_minutes"] < 120:
        steps.append("Schedule a 2-hour deep-work block with the browser extension on.")
    if data["study_minutes"] < 60:
        steps.append("Block 25 minutes for focused study.")
    if data["vocab_events"] == 0:
        steps.append("Run one GRE vocab cycle to keep retention sharp.")
    if data["math_attempts"] == 0:
        steps.append("Complete one math practice set (enable Math Tutor plugin).")
    ocr_samples = data.get("ocr_samples", 0)
    if ocr_samples and ocr_samples < 20:
        steps.append(f"Keep training handwriting — {ocr_samples} OCR samples logged so far.")
    if not steps:
        steps.append("Maintain today's habits — metrics look balanced.")

    return ReviewOut(
        comments=comments,
        next_steps=steps,
        goals=["Protect sleep", "One focused study block", "Track mood daily"],
        overall_performance=perf,
        source="template",
    )


@router.post("/review", response_model=ReviewOut)
async def insights_review(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    from backend.hub.services.coach_context import build_coach_context

    daily = insights_daily(db=db, user=user)
    context = build_coach_context(db, user, daily=daily)

    from backend.integrations.nim_client import nim_available

    if nim_available():
        try:
            from backend.hub.services.gemma_review import generate_daily_review

            gemma = await generate_daily_review(context.get("today", daily), user_id=user.id)
            return ReviewOut(**gemma)
        except Exception:
            pass

    from backend.hub.services.local_coach import generate_local_review, local_llm_available

    if local_llm_available():
        try:
            local = generate_local_review(context)
            return ReviewOut(**local)
        except Exception:
            pass

    return _template_review(context.get("today", daily))


def _hub_context(db: Session, user: User) -> dict:
    from backend.hub.services.coach_context import build_coach_context

    daily = insights_daily(db=db, user=user)
    return build_coach_context(db, user, daily=daily)


@router.get("/context")
def insights_context(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Summary of what the AI coach can see for this user (for UI transparency)."""
    return _hub_context(db, user)


@router.get("/knowledge")
def insights_knowledge(
    q: str = "",
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Preview what the coach would retrieve for a question (transparency / debug)."""
    from backend.hub.services.coach_knowledge import retrieve_coach_knowledge

    kb = retrieve_coach_knowledge(db, user.id, q)
    return {
        "query_keywords": kb["query_keywords"],
        "index": kb["index"],
        "vocab_count": len(kb["vocab"]),
        "lecture_notes_count": len(kb["lecture_notes"]),
        "math_count": len(kb["math_recent"]),
        "transcript_snippet_count": len(kb["transcript_snippets"]),
        "browser_events": kb.get("browser_activity", {}).get("events_parsed", 0),
        "browser_study_signals": kb.get("browser_activity", {}).get("study_signals", [])[:5],
        "vocab_preview": kb["vocab"][:5],
        "lecture_preview": [
            {"title": n["title"], "topic": n["topic"], "excerpt_chars": len(n.get("excerpt") or "")}
            for n in kb["lecture_notes"]
        ],
    }


@router.post("/chat", response_model=ChatResponse)
def insights_chat(body: ChatRequest, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    from backend.core.ollama_client import llm_reachable
    from backend.hub.services.local_coach import chat_with_coach, local_llm_available

    context = _hub_context(db, user)
    msgs = [{"role": m.role, "content": m.content} for m in body.messages if m.content.strip()]

    from backend.hub.services.coach_knowledge import retrieve_coach_knowledge

    last_query = msgs[-1]["content"] if msgs else ""
    context["knowledge_base"] = retrieve_coach_knowledge(db, user.id, last_query)

    if local_llm_available():
        try:
            reply = chat_with_coach(msgs, hub_context=context)
            return ChatResponse(reply=reply, source="gemma", llm_available=True)
        except Exception as exc:
            return ChatResponse(
                reply=f"I couldn't reach the local model ({exc}). Check LM Studio on port 1234.",
                source="template",
                llm_available=llm_reachable(),
            )

    if not msgs:
        review = _template_review(context.get("today", {}))
        return ChatResponse(
            reply=review.comments,
            source="template",
            llm_available=False,
        )

    last = msgs[-1]["content"].lower()
    if "sleep" in last:
        tip = "Protect 7+ hours tonight — your sleep minutes look low in today's hub data."
    elif "vocab" in last or "gre" in last:
        tip = "Run one GRE vocab cycle: Read → Quiz → Report, then revisit low-mastery words."
    elif "math" in last:
        tip = "Try one Math Tutor practice set and log your attempts so the hub can track progress."
    else:
        review = _template_review(context.get("today", {}))
        tip = review.comments

    return ChatResponse(reply=tip, source="template", llm_available=llm_reachable())


@router.get("/agent/snapshot")
def agent_codebase_snapshot(
    refresh: bool = False,
    user: User = Depends(get_current_user),
):
    """Codebase overview for Project Agent UI."""
    from backend.hub.services.codebase_agent import build_codebase_snapshot

    _ = user
    return build_codebase_snapshot(force=refresh)


@router.get("/agent/files")
def agent_list_files(
    q: str = "",
    user: User = Depends(get_current_user),
):
    from backend.hub.services.codebase_agent import list_browse_files

    _ = user
    return {"files": list_browse_files(q, limit=100)}


@router.get("/agent/file")
def agent_read_file(
    path: str,
    user: User = Depends(get_current_user),
):
    from backend.hub.services.codebase_agent import read_project_file

    _ = user
    try:
        return read_project_file(path)
    except (ValueError, FileNotFoundError) as exc:
        from fastapi import HTTPException

        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/agent/chat", response_model=ChatResponse)
def agent_chat(body: ChatRequest, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Project Agent: Gemma + codebase file access (pairs with Cursor)."""
    from backend.core.ollama_client import llm_reachable
    from backend.hub.services.project_agent import chat_with_project_agent, project_agent_available

    context = _hub_context(db, user)
    msgs = [{"role": m.role, "content": m.content} for m in body.messages if m.content.strip()]
    last_query = msgs[-1]["content"] if msgs else ""

    if project_agent_available():
        try:
            reply = chat_with_project_agent(msgs, hub_context=context, last_query=last_query)
            return ChatResponse(reply=reply, source="gemma", llm_available=True)
        except Exception as exc:
            return ChatResponse(
                reply=f"Project Agent could not reach Gemma ({exc}). Check OLLAMA_ENABLED=1 and LM Studio.",
                source="template",
                llm_available=llm_reachable(),
            )

    return ChatResponse(
        reply="Enable OLLAMA_ENABLED=1 and start LM Studio to use the Project Agent with codebase access.",
        source="template",
        llm_available=False,
    )
