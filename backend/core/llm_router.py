"""External LLM completion API for script clients."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from backend.core.auth import get_current_user
from backend.core.llm_gateway import llm_complete
from backend.core.ollama_client import LlmOptions
from backend.models import User

router = APIRouter(prefix="/api/llm", tags=["llm"])


class CompleteRequest(BaseModel):
    prompt: str = Field(..., min_length=1, max_length=300_000)
    task: str = Field(default="generic", max_length=64)
    tier: str | None = Field(default=None, max_length=16)
    system_prompt: str | None = Field(default=None, max_length=20_000)
    timeout: float = Field(default=120.0, ge=1.0, le=600.0)
    route_profile: str | None = Field(default=None, max_length=32)
    llm_provider: str | None = Field(default=None, max_length=32)
    llm_base_url: str | None = Field(default=None, max_length=200)
    llm_model: str | None = Field(default=None, max_length=120)
    confirm_heavy_budget: bool = False


@router.post("/complete")
def post_complete(body: CompleteRequest, _user: User = Depends(get_current_user)):
    llm_override = None
    if any([body.llm_provider, body.llm_base_url, body.llm_model]):
        llm_override = LlmOptions(
            provider=body.llm_provider,
            base_url=body.llm_base_url,
            model=body.llm_model,
        )

    result = llm_complete(
        body.prompt,
        task=body.task.strip().lower() or "generic",
        tier=body.tier.strip().lower() if isinstance(body.tier, str) and body.tier.strip() else None,
        system_prompt=body.system_prompt,
        timeout=body.timeout,
        llm=llm_override,
        confirm_heavy_budget=body.confirm_heavy_budget,
        route_profile=body.route_profile,
    )
    if result.error == "budget_exceeded":
        raise HTTPException(status_code=402, detail="heavy_budget_exceeded")
    if result.error == "context_too_long":
        raise HTTPException(status_code=413, detail="context_too_long")
    if result.error or not result.text:
        raise HTTPException(status_code=503, detail=result.error or "all_failed")
    return {
        "text": result.text,
        "tier": result.tier,
        "provider": result.provider,
        "model": result.model,
        "route_profile": result.route_profile,
        "fallback_used": result.fallback_used,
        "latency_ms": result.latency_ms,
        "prompt_tokens": result.prompt_tokens,
        "completion_tokens": result.completion_tokens,
        "total_tokens": result.total_tokens,
        "generation_id": result.generation_id,
        "upstream_provider": result.upstream_provider,
        "estimated_cost": result.estimated_cost,
        "attempts": result.attempts or [],
    }

