"""In-memory job tracker for long-running corpus setup tasks."""

from __future__ import annotations

import threading
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Callable


@dataclass
class CorpusJob:
    job_id: str
    kind: str
    status: str = "queued"  # queued | running | done | error
    progress: float = 0.0
    message: str = ""
    logs: list[str] = field(default_factory=list)
    result: dict[str, Any] | None = None
    error: str | None = None
    started_at: str = ""
    finished_at: str = ""


_lock = threading.Lock()
_jobs: dict[str, CorpusJob] = {}
_latest_job_id: str | None = None


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _append_log(job: CorpusJob, line: str) -> None:
    job.logs.append(line)
    if len(job.logs) > 400:
        job.logs = job.logs[-400:]
    job.message = line


def get_job(job_id: str | None = None) -> CorpusJob | None:
    with _lock:
        jid = job_id or _latest_job_id
        if not jid:
            return None
        return _jobs.get(jid)


def start_job(kind: str, worker: Callable[[CorpusJob], dict[str, Any] | None]) -> CorpusJob:
    job = CorpusJob(job_id=str(uuid.uuid4()), kind=kind, started_at=_now())
    with _lock:
        global _latest_job_id
        _jobs[job.job_id] = job
        _latest_job_id = job.job_id

    def _run() -> None:
        job.status = "running"
        _append_log(job, f"Started {kind}")
        try:
            result = worker(job)
            job.result = result or {}
            job.status = "done"
            job.progress = 1.0
            _append_log(job, "Finished successfully")
        except Exception as exc:  # noqa: BLE001
            job.status = "error"
            job.error = str(exc)
            _append_log(job, f"Error: {exc}")
        finally:
            job.finished_at = _now()

    threading.Thread(target=_run, daemon=True).start()
    return job


def job_to_dict(job: CorpusJob) -> dict[str, Any]:
    return {
        "job_id": job.job_id,
        "kind": job.kind,
        "status": job.status,
        "progress": round(job.progress, 3),
        "message": job.message,
        "logs": job.logs[-120:],
        "result": job.result,
        "error": job.error,
        "started_at": job.started_at,
        "finished_at": job.finished_at,
    }
