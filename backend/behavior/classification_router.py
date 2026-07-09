"""On-demand LLM classification review endpoints."""

from __future__ import annotations

import json
import logging
import shutil
from datetime import UTC, datetime
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.core.auth import get_current_user
from backend.db.session import get_db
from backend.models import User
from backend.models.app_classification import (
    AppClassificationCache,
    AppClassificationSuggestion,
)
from backend.behavior.classification_service import (
    ALLOWED_CATEGORIES,
    backfill_approved,
    classify_key_via_llm,
    classify_key_via_rules,
    find_uncategorized_keys,
    preview_impact,
    revert_backfill,
)
from backend.paths import DB_PATH

log = logging.getLogger("classification")
router = APIRouter(prefix="/api/classification", tags=["classification"])

_BACKUP_FLAG = DB_PATH.parent / ".classification_backup_done"


def _ensure_backup() -> None:
    if _BACKUP_FLAG.exists():
        return
    if DB_PATH.exists():
        backup = DB_PATH.parent / f"vocab_app.backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
        try:
            shutil.copy2(DB_PATH, backup)
            log.info("SQLite backup created: %s", backup.name)
        except OSError as exc:
            log.warning("Backup failed: %s", exc)
    _BACKUP_FLAG.parent.mkdir(parents=True, exist_ok=True)
    _BACKUP_FLAG.write_text("1")


def _get_suggestion(db: Session, suggestion_id: int) -> AppClassificationSuggestion:
    row = db.get(AppClassificationSuggestion, suggestion_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Suggestion not found")
    return row


def _serialize_suggestion(s: AppClassificationSuggestion) -> dict:
    titles = []
    if s.sample_titles:
        try:
            titles = json.loads(s.sample_titles)
        except json.JSONDecodeError:
            titles = []
    return {
        "id": s.id,
        "key": s.key,
        "key_type": s.key_type,
        "suggested_category": s.suggested_category,
        "confidence": s.confidence,
        "sample_titles": titles,
        "occurrence_count": s.occurrence_count,
        "status": s.status,
        "reviewed_at": s.reviewed_at.isoformat() if s.reviewed_at else None,
        "created_at": s.created_at.isoformat() if s.created_at else None,
    }


def _do_approve(
    db: Session,
    suggestion: AppClassificationSuggestion,
    category: str,
) -> int:
    existing = db.query(AppClassificationCache).filter(
        AppClassificationCache.key == suggestion.key,
    ).first()
    if existing:
        existing.category = category
        existing.source = "llm_reviewed"
    else:
        db.add(AppClassificationCache(
            key=suggestion.key,
            key_type=suggestion.key_type,
            category=category,
            source="llm_reviewed",
        ))
    db.flush()

    affected = backfill_approved(db, suggestion.key, suggestion.key_type, category)
    suggestion.status = "approved"
    suggestion.reviewed_at = datetime.now(UTC)
    db.commit()
    return affected


class ScanBody(BaseModel):
    limit: int = 20
    llm_tier: str | None = None
    confirm_heavy_budget: bool = False


@router.post("/scan", response_model=dict)
def scan_uncategorized(
    body: ScanBody = ScanBody(),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    from backend.config import get_settings
    from backend.core.llm_request import guard_heavy_budget, tier_from_body
    from backend.core.ollama_client import llm_reachable

    _ensure_backup()
    guard_heavy_budget(body)
    tier = tier_from_body(body)
    keys = find_uncategorized_keys(db, limit=body.limit)
    created: list[dict] = []
    llm_error: str | None = None
    needs_llm = False

    for item in keys:
        existing = db.query(AppClassificationSuggestion).filter(
            AppClassificationSuggestion.key == item["key"],
            AppClassificationSuggestion.status == "pending",
        ).first()
        if existing:
            created.append(_serialize_suggestion(existing))
            continue

        rule_result = classify_key_via_rules(
            item["key"],
            item["key_type"],
            item["sample_titles"],
        )
        if rule_result is not None:
            category, confidence = rule_result
        else:
            needs_llm = True
            if llm_error:
                continue
            if get_settings().ollama_enabled and not llm_reachable():
                llm_error = "unreachable"
                continue
            result = classify_key_via_llm(
                item["key"],
                item["key_type"],
                item["sample_titles"],
                llm_tier=tier,
            )
            if result is None:
                continue
            category, confidence = result

        suggestion = AppClassificationSuggestion(
            key=item["key"],
            key_type=item["key_type"],
            suggested_category=category,
            confidence=confidence,
            sample_titles=json.dumps(item["sample_titles"]),
            occurrence_count=item["occurrence_count"],
            status="pending",
        )
        db.add(suggestion)
        db.flush()
        db.refresh(suggestion)
        created.append(_serialize_suggestion(suggestion))

    db.commit()
    payload: dict = {"suggestions": created, "scanned": len(keys), "created": len(created)}
    if llm_error:
        payload["llm_error"] = llm_error
    elif needs_llm and not created and keys and get_settings().ollama_enabled and not llm_reachable():
        payload["llm_error"] = "unreachable"
    return payload


@router.get("/pending", response_model=dict)
def list_pending(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    rows = (
        db.query(AppClassificationSuggestion)
        .filter(AppClassificationSuggestion.status == "pending")
        .order_by(AppClassificationSuggestion.occurrence_count.desc())
        .all()
    )
    return {"suggestions": [_serialize_suggestion(r) for r in rows]}


@router.get("/{suggestion_id}/preview", response_model=dict)
def preview_suggestion(
    suggestion_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    suggestion = _get_suggestion(db, suggestion_id)
    impact = preview_impact(db, suggestion.key, suggestion.key_type)
    return {
        "suggestion": _serialize_suggestion(suggestion),
        "impact": impact,
    }


@router.post("/{suggestion_id}/approve", response_model=dict)
def approve_suggestion(
    suggestion_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    suggestion = _get_suggestion(db, suggestion_id)
    if suggestion.status != "pending":
        raise HTTPException(status_code=400, detail=f"Suggestion is already {suggestion.status}")
    affected = _do_approve(db, suggestion, suggestion.suggested_category)
    return {"status": "approved", "affected_rows": affected}


class RejectBody(BaseModel):
    override_category: Optional[str] = None


@router.post("/{suggestion_id}/reject", response_model=dict)
def reject_suggestion(
    suggestion_id: int,
    body: RejectBody = RejectBody(),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    suggestion = _get_suggestion(db, suggestion_id)
    if suggestion.status != "pending":
        raise HTTPException(status_code=400, detail=f"Suggestion is already {suggestion.status}")

    if body.override_category and body.override_category.strip():
        cat = body.override_category.strip()
        if cat not in ALLOWED_CATEGORIES:
            raise HTTPException(status_code=400, detail=f"Invalid category: {cat}")
        affected = _do_approve(db, suggestion, cat)
        suggestion.status = "approved"
        db.commit()
        return {"status": "approved_override", "category": cat, "affected_rows": affected}

    suggestion.status = "rejected"
    suggestion.reviewed_at = datetime.now(UTC)
    db.commit()
    return {"status": "rejected"}


class EditApproveBody(BaseModel):
    category: str


@router.post("/{suggestion_id}/edit-and-approve", response_model=dict)
def edit_and_approve(
    suggestion_id: int,
    body: EditApproveBody,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    suggestion = _get_suggestion(db, suggestion_id)
    if suggestion.status != "pending":
        raise HTTPException(status_code=400, detail=f"Suggestion is already {suggestion.status}")
    cat = body.category.strip()
    if cat not in ALLOWED_CATEGORIES:
        raise HTTPException(status_code=400, detail=f"Invalid category: {cat}")
    affected = _do_approve(db, suggestion, cat)
    return {"status": "approved", "category": cat, "affected_rows": affected}


@router.post("/{suggestion_id}/revert", response_model=dict)
def revert_suggestion(
    suggestion_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    suggestion = _get_suggestion(db, suggestion_id)
    if suggestion.status != "approved":
        raise HTTPException(status_code=400, detail="Can only revert approved suggestions")
    reverted = revert_backfill(db, suggestion.key, suggestion.key_type)
    db.query(AppClassificationCache).filter(
        AppClassificationCache.key == suggestion.key,
    ).delete()
    suggestion.status = "reverted"
    suggestion.reviewed_at = datetime.now(UTC)
    db.commit()
    return {"status": "reverted", "reverted_rows": reverted}
