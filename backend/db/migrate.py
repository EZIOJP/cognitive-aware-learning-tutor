"""Runtime migration checks — Alembic is the only schema authority."""

from __future__ import annotations

import logging
import time
from pathlib import Path

from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory

from backend.config import get_settings
from backend.db.base import engine

log = logging.getLogger(__name__)

_rev_cache: tuple[float, str | None, str | None] = (0.0, None, None)
_REV_CACHE_S = 30.0


def _alembic_config() -> Config:
    root = Path(__file__).resolve().parents[2]
    cfg = Config(str(root / "alembic.ini"))
    cfg.set_main_option("sqlalchemy.url", get_settings().database_url)
    return cfg


def get_revision_state(*, use_cache: bool = True) -> tuple[str | None, str | None]:
    """Return (current_revision, head_revision)."""
    global _rev_cache
    now = time.monotonic()
    if (
        use_cache
        and _rev_cache[1] is not None
        and (now - _rev_cache[0]) < _REV_CACHE_S
    ):
        return _rev_cache[1], _rev_cache[2]

    cfg = _alembic_config()
    script = ScriptDirectory.from_config(cfg)
    head = script.get_current_head()
    with engine.connect() as conn:
        ctx = MigrationContext.configure(conn)
        current = ctx.get_current_revision()
    _rev_cache = (now, current, head)
    return current, head


def is_at_head() -> bool:
    current, head = get_revision_state()
    return current == head


def ensure_at_head(*, strict: bool | None = None) -> None:
    """
    Warn or fail if DB schema revision is behind Alembic head.
    strict=True  -> raise RuntimeError
    strict=False -> log warning only
    strict=None  -> strict when dev_mode is False
    """
    settings = get_settings()
    if strict is None:
        strict = not settings.dev_mode

    current, head = get_revision_state(use_cache=False)
    if current == head:
        return

    if settings.dev_mode:
        try:
            from alembic import command

            log.warning(
                "Database schema is at %r, head is %r — auto-upgrading (dev_mode).",
                current,
                head,
            )
            command.upgrade(_alembic_config(), "head")
            current, head = get_revision_state(use_cache=False)
            if current == head:
                log.info("Database schema upgraded to %r.", head)
                return
        except Exception as exc:
            log.warning("Auto-upgrade failed: %s", exc)

    msg = (
        f"Database schema is at revision {current!r}, but Alembic head is {head!r}. "
        "Run: python -m alembic upgrade head"
    )
    if strict:
        raise RuntimeError(msg)
    log.warning(msg)


def revision_history() -> list[str]:
    cfg = _alembic_config()
    script = ScriptDirectory.from_config(cfg)
    return [rev.revision for rev in script.walk_revisions(base="base", head="heads")]
