"""Daily soft cap for heavy-tier cloud LLM calls."""

from __future__ import annotations

import json
import logging
from datetime import date
from pathlib import Path

from backend.config import get_settings
from backend.paths import LLM_USAGE_DIR

log = logging.getLogger(__name__)


def _usage_path(day: date | None = None) -> Path:
    d = day or date.today()
    LLM_USAGE_DIR.mkdir(parents=True, exist_ok=True)
    return LLM_USAGE_DIR / f"{d.isoformat()}.json"


def _read_usage(path: Path) -> dict:
    if not path.is_file():
        return {"heavy_calls": 0}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return {"heavy_calls": int(data.get("heavy_calls", 0))}
    except (json.JSONDecodeError, OSError, TypeError, ValueError):
        return {"heavy_calls": 0}


def _write_usage(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def heavy_budget_status() -> dict:
    cap = get_settings().llm_heavy_daily_soft_cap
    used = _read_usage(_usage_path())["heavy_calls"]
    return {
        "used": used,
        "cap": cap,
        "exceeded": cap > 0 and used >= cap,
    }


def heavy_budget_allows(*, confirm: bool = False) -> bool:
    status = heavy_budget_status()
    if status["cap"] <= 0:
        return True
    if status["used"] < status["cap"]:
        return True
    if confirm:
        return True
    log.warning(
        "Heavy tier daily soft cap reached (%s/%s) — set confirm_heavy_budget or lower tier",
        status["used"],
        status["cap"],
    )
    return False


def record_heavy_cloud_call() -> None:
    path = _usage_path()
    data = _read_usage(path)
    data["heavy_calls"] = int(data.get("heavy_calls", 0)) + 1
    _write_usage(path, data)
