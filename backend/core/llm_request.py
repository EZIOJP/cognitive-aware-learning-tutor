"""Shared LLM request-body helpers for FastAPI routers."""

from __future__ import annotations

from fastapi import HTTPException

from backend.core.ollama_client import LlmOptions


def tier_from_body(body: object) -> str | None:
    tier = getattr(body, "llm_tier", None)
    return tier.strip().lower() if isinstance(tier, str) and tier.strip() else None


def confirm_budget_from_body(body: object) -> bool:
    return bool(getattr(body, "confirm_heavy_budget", False))


def guard_heavy_budget(body: object) -> None:
    """Reject heavy-tier requests over the daily soft cap before doing any work."""
    if tier_from_body(body) != "heavy" or confirm_budget_from_body(body):
        return
    from backend.core.llm_budget import heavy_budget_status

    status = heavy_budget_status()
    if status["exceeded"]:
        raise HTTPException(
            status_code=402,
            detail=(
                f"heavy_budget_exceeded: Daily heavy-tier cloud cap reached "
                f"({status['used']}/{status['cap']}). Confirm to continue anyway."
            ),
        )


def llm_override_from_body(body: object) -> LlmOptions | None:
    provider = getattr(body, "llm_provider", None)
    base_url = getattr(body, "llm_base_url", None)
    model = getattr(body, "llm_model", None)
    if not any([provider, base_url, model]):
        return None
    return LlmOptions(
        provider=provider,
        base_url=base_url,
        model=model,
    )
