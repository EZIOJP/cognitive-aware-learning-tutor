"""System diagnostics — log file listing and tail for the Study Library UI."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Depends
from pydantic import BaseModel, ConfigDict, Field

from backend.core.log_setup import list_log_files, log_error, resolve_log_path, tail_log_file
from backend.config import get_settings
from backend.core.auth import get_current_user
from backend.core.llm_env import get_llm_env_status
from backend.core.env_store import ALLOWED_ENV_KEYS, patch_env
from backend.core.llm_probe import test_chain_entry, test_chain_entry_from_parts, test_tier_chain
from backend.models.user import User
from backend.paths import LOGS_DIR

router = APIRouter(prefix="/api/system", tags=["system"])
log = logging.getLogger(__name__)


class ClientLogEntry(BaseModel):
    level: str = "error"
    message: str
    context: str | None = None
    url: str | None = None
    stack: str | None = None


class LlmKeysPatch(BaseModel):
    """Partial .env update — use env var names. Empty string removes a key."""

    model_config = ConfigDict(extra="ignore")

    LLM_CLOUD_API_KEY: str | None = None
    GEMINI_API_KEY: str | None = None
    GROQ_API_KEY: str | None = None
    CEREBRAS_API_KEY: str | None = None
    MISTRAL_API_KEY: str | None = None
    GITHUB_TOKEN: str | None = None
    LLM_OPENROUTER_API_KEY: str | None = None
    LLM_ANTHROPIC_API_KEY: str | None = None
    NIM_API_KEY: str | None = None
    LLM_API_KEY: str | None = None
    TAVILY_API_KEY: str | None = None
    LLM_ROUTE_PROFILE: str | None = None
    OLLAMA_URL: str | None = None
    LMSTUDIO_URL: str | None = None
    OLLAMA_NATIVE_URL: str | None = None
    OLLAMA_MODEL: str | None = None
    LLM_PROVIDER: str | None = None
    OLLAMA_ENABLED: str | None = None


class LlmTestRequest(BaseModel):
    entry: str | None = None
    provider: str | None = None
    model: str | None = None
    base_url: str | None = None
    api_key: str | None = None


class LlmTestChainRequest(BaseModel):
    tier: str = "medium"
    route_profile: str | None = None
    task: str = "generic"


class LlmTestAllProfilesRequest(BaseModel):
    task: str = "generic"
    profiles: list[str] | None = None


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


@router.get("/llm/env")
def get_llm_env(_user: User = Depends(get_current_user)) -> dict[str, Any]:
    """Masked API key status and server-side task tier defaults."""
    return get_llm_env_status()


@router.patch("/llm/keys")
def patch_llm_keys(body: LlmKeysPatch, _user: User = Depends(get_current_user)) -> dict[str, Any]:
    """Update LLM-related keys in repo .env (whitelisted vars only)."""
    dumped = body.model_dump(exclude_unset=True)
    updates: dict[str, str] = {}
    for key, value in dumped.items():
        upper = str(key).strip().upper()
        if upper not in ALLOWED_ENV_KEYS or value is None:
            continue
        updates[upper] = value
    if not updates:
        raise HTTPException(
            status_code=400,
            detail="No allowed keys in request — paste a key value then Save (empty drafts are skipped)",
        )
    written = patch_env(updates)
    return {"status": "ok", "written": written, "env": get_llm_env_status()}


@router.post("/llm/test")
def test_llm_provider(body: LlmTestRequest, _user: User = Depends(get_current_user)) -> dict[str, Any]:
    """Probe one provider chain entry or explicit provider/model/url."""
    if body.entry:
        return test_chain_entry(body.entry, api_key_override=body.api_key)
    if body.provider and body.model:
        return test_chain_entry_from_parts(
            provider=body.provider,
            model=body.model,
            base_url=body.base_url,
            api_key=body.api_key,
        )
    raise HTTPException(status_code=400, detail="Provide entry or provider+model")


@router.post("/llm/test-chain")
def test_llm_chain(body: LlmTestChainRequest, _user: User = Depends(get_current_user)) -> dict[str, Any]:
    """Probe every configured entry in the active tier chain."""
    tier = body.tier.strip().lower()
    if tier not in ("light", "medium", "heavy"):
        raise HTTPException(status_code=400, detail="tier must be light, medium, or heavy")
    return test_tier_chain(tier, route_profile=body.route_profile, task=body.task)


@router.post("/llm/test-all-profiles", status_code=202)
def test_all_route_profiles(
    body: LlmTestAllProfilesRequest,
    _user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """Enqueue light/medium/heavy probes for every route profile (Huey). Poll GET /llm/jobs/{id}."""
    from backend.core.llm_jobs import enqueue_test_all_profiles
    from backend.core.llm_routes import load_route_profiles

    available = load_route_profiles()
    if not available:
        raise HTTPException(status_code=404, detail="No route profiles in data/llm_routes.json")

    if body.profiles:
        wanted = {p.strip().lower() for p in body.profiles if p.strip()}
        names = [n for n in sorted(available.keys()) if n in wanted]
        if not names:
            raise HTTPException(status_code=400, detail="No matching route profiles")
        profiles = names
    else:
        profiles = None

    try:
        job_id = enqueue_test_all_profiles(task=body.task, profiles=profiles)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"job_id": job_id, "status": "queued"}


@router.get("/llm/jobs/{job_id}")
def get_llm_job(job_id: str, _user: User = Depends(get_current_user)) -> dict[str, Any]:
    """Poll status for an enqueued LLM probe job."""
    from backend.core.llm_jobs import get_job

    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job
