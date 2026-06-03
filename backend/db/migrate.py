"""Runtime migration checks — Alembic is the only schema authority."""

from __future__ import annotations

import logging
from pathlib import Path

from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory

from backend.config import get_settings
from backend.db.base import engine

log = logging.getLogger(__name__)


def _alembic_config() -> Config:
    root = Path(__file__).resolve().parents[2]
    cfg = Config(str(root / "alembic.ini"))
    cfg.set_main_option("sqlalchemy.url", get_settings().database_url)
    return cfg


def get_revision_state() -> tuple[str | None, str | None]:
    """Return (current_revision, head_revision)."""
    cfg = _alembic_config()
    script = ScriptDirectory.from_config(cfg)
    head = script.get_current_head()
    with engine.connect() as conn:
        ctx = MigrationContext.configure(conn)
        current = ctx.get_current_revision()
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

    current, head = get_revision_state()
    if current == head:
        return

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
