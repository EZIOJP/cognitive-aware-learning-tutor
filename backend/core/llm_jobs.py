"""Huey SQLite queue for long LLM chain probes (test-all-profiles)."""

from __future__ import annotations

import json
import logging
import os
import uuid
from pathlib import Path
from typing import Any

from huey import SqliteHuey

from backend.paths import ROOT

log = logging.getLogger(__name__)

HUEY_DB = ROOT / "data" / "huey.db"
JOBS_DIR = ROOT / "data" / "llm_jobs"


def _huey_immediate() -> bool:
    flag = os.environ.get("HUEY_IMMEDIATE", "").strip().lower()
    if flag in ("1", "true", "yes"):
        return True
    if flag in ("0", "false", "no"):
        return False
    return "PYTEST_CURRENT_TEST" in os.environ


HUEY_DB.parent.mkdir(parents=True, exist_ok=True)
JOBS_DIR.mkdir(parents=True, exist_ok=True)

huey = SqliteHuey(
    name="calt-llm",
    filename=str(HUEY_DB),
    immediate=_huey_immediate(),
)


def _job_path(job_id: str) -> Path:
    safe = "".join(c for c in job_id if c.isalnum() or c in "-_")
    return JOBS_DIR / f"{safe}.json"


def write_job(job_id: str, payload: dict[str, Any]) -> None:
    path = _job_path(job_id)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def read_job(job_id: str) -> dict[str, Any] | None:
    path = _job_path(job_id)
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def run_test_all_profiles_sync(
    *,
    task: str = "generic",
    profiles: list[str] | None = None,
) -> dict[str, Any]:
    """Synchronous matrix probe (also used by the Huey worker task)."""
    from backend.config import get_settings
    from backend.core.llm_probe import test_tier_chain
    from backend.core.llm_routes import load_route_profiles

    available = load_route_profiles()
    if not available:
        raise ValueError("No route profiles in data/llm_routes.json")

    names = sorted(available.keys())
    if profiles:
        wanted = {p.strip().lower() for p in profiles if p and str(p).strip()}
        names = [n for n in names if n in wanted]
        if not names:
            raise ValueError("No matching route profiles")

    profiles_out: dict[str, Any] = {}
    for name in names:
        tiers_out: dict[str, Any] = {}
        for tier in ("light", "medium", "heavy"):
            tiers_out[tier] = test_tier_chain(tier, route_profile=name, task=task)
        profiles_out[name] = {
            "tiers": tiers_out,
            "reachable": any(t.get("reachable") for t in tiers_out.values()),
        }

    active = get_settings().llm_route_profile.strip().lower() or "local"
    reachable_count = sum(1 for p in profiles_out.values() if p.get("reachable"))
    return {
        "task": task,
        "active_profile": active,
        "profiles": profiles_out,
        "summary": {
            "total": len(profiles_out),
            "reachable": reachable_count,
        },
    }


@huey.task()
def test_all_profiles_task(
    job_id: str,
    task: str = "generic",
    profiles: list[str] | None = None,
) -> dict[str, Any]:
    write_job(
        job_id,
        {
            "job_id": job_id,
            "kind": "test_all_profiles",
            "status": "running",
            "task": task,
            "profiles": profiles,
        },
    )
    try:
        result = run_test_all_profiles_sync(task=task, profiles=profiles)
        write_job(
            job_id,
            {
                "job_id": job_id,
                "kind": "test_all_profiles",
                "status": "completed",
                "task": task,
                "result": result,
            },
        )
        return result
    except Exception as exc:
        log.exception("test_all_profiles_task failed job_id=%s", job_id)
        write_job(
            job_id,
            {
                "job_id": job_id,
                "kind": "test_all_profiles",
                "status": "failed",
                "task": task,
                "error": str(exc),
            },
        )
        raise


def enqueue_test_all_profiles(
    *,
    task: str = "generic",
    profiles: list[str] | None = None,
) -> str:
    job_id = str(uuid.uuid4())
    write_job(
        job_id,
        {
            "job_id": job_id,
            "kind": "test_all_profiles",
            "status": "queued",
            "task": task,
            "profiles": profiles,
        },
    )
    test_all_profiles_task(job_id, task=task, profiles=profiles)
    return job_id


def get_job(job_id: str) -> dict[str, Any] | None:
    return read_job(job_id)
