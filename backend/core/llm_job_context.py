"""Job-sticky LLM tier — lock tier for multi-chunk generation jobs."""

from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass

_CURRENT_JOB: ContextVar["LlmJobContext | None"] = ContextVar("llm_job_context", default=None)


@dataclass(frozen=True)
class LlmJobContext:
    tier: str | None
    task: str
    locked: bool = True


def get_job_context() -> LlmJobContext | None:
    return _CURRENT_JOB.get()


@contextmanager
def llm_job(tier: str | None = None, task: str = "notes_job"):
    token = _CURRENT_JOB.set(LlmJobContext(tier=tier, task=task, locked=True))
    try:
        yield
    finally:
        _CURRENT_JOB.reset(token)
