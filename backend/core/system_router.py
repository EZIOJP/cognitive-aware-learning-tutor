"""System diagnostics — log file listing and tail for the Study Library UI."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from backend.core.log_setup import list_log_files, log_error, resolve_log_path, tail_log_file
from backend.paths import LOGS_DIR

router = APIRouter(prefix="/api/system", tags=["system"])
log = logging.getLogger(__name__)


class ClientLogEntry(BaseModel):
    level: str = "error"
    message: str
    context: str | None = None
    url: str | None = None
    stack: str | None = None


@router.get("/logs")
def get_logs() -> dict[str, Any]:
    """List log files the UI and Python GUI can open for debugging."""
    return {
        "logs_dir": str(LOGS_DIR.resolve()),
        "files": list_log_files(),
    }


@router.get("/logs/tail")
def tail_logs(
    file: str = Query("backend.log", description="Log file name under data/logs/"),
    lines: int = Query(200, ge=10, le=2000),
) -> dict[str, Any]:
    try:
        path = resolve_log_path(file)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {
        "file": file,
        "path": str(path),
        "lines": lines,
        "content": tail_log_file(file, max_lines=lines),
    }


@router.post("/logs/client")
def ingest_client_log(body: ClientLogEntry) -> dict[str, str]:
    """Frontend / browser errors — appended to backend.log for one debug trail."""
    level = body.level.lower()
    msg = f"[client] {body.message}"
    if body.context:
        msg = f"{msg} | {body.context}"
    if body.url:
        msg = f"{msg} | url={body.url}"
    logger = logging.getLogger("backend.client")
    if level == "warning":
        logger.warning(msg)
    elif level == "info":
        logger.info(msg)
    else:
        logger.error(msg)
        if body.stack:
            logger.error("stack:\n%s", body.stack[:8000])
    return {"status": "ok", "logged_at": datetime.now(timezone.utc).isoformat()}
