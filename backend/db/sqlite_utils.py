"""SQLite concurrency helpers (API + desktop tracker share vocab_app.db)."""

from __future__ import annotations

import time

from sqlalchemy import event
from sqlalchemy.engine import Engine
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session


def configure_sqlite_engine(engine: Engine, *, busy_timeout_ms: int = 10000) -> None:
    """WAL + busy_timeout so tracker writes do not fail planner imports."""

    @event.listens_for(engine, "connect")
    def _on_connect(dbapi_conn, _connection_record) -> None:  # noqa: ANN001
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute(f"PRAGMA busy_timeout={busy_timeout_ms}")
        cursor.close()


def commit_with_retry(db: Session, *, retries: int = 8) -> None:
    for attempt in range(retries):
        try:
            db.commit()
            return
        except OperationalError as exc:
            db.rollback()
            if "locked" in str(exc).lower() and attempt < retries - 1:
                time.sleep(0.15 * (attempt + 1))
                continue
            raise
