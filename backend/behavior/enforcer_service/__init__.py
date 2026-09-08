"""LEGACY Python hard-block enforcer — fallback only.

Prefer native ``calt_enforcer.exe`` (zero-Python tracker). Do not extend this
module. SoftLand / Focus stay on FastAPI; kills belong to the C++ service.
"""

from __future__ import annotations

from backend.behavior.enforcer_service.service import (
    enforce_once,
    main,
    resolve_enforcer_user_id,
    run_loop,
)

__all__ = ["enforce_once", "resolve_enforcer_user_id", "run_loop", "main"]
