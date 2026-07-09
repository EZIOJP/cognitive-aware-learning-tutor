"""Local persistence: SQLite, CSV backup, checkpoint, config."""

from __future__ import annotations

import csv
import json
import logging
import os
import time
from dataclasses import asdict, dataclass, field
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

from sqlalchemy import func, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from backend.core.auth import ensure_demo_user
from backend.db.base import SessionLocal, engine
from backend.models.timetable import TrackedSession
from backend.paths import DATA_LOGS_DIR, LOGS_DIR
from backend.timetable.tracker_bridge import ingest_desktop_session

log = logging.getLogger("desktop_tracker")

APP_DATA_DIR = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local")) / "CognitiveAwareTutor"
CONFIG_PATH = APP_DATA_DIR / "tracker.json"
CHECKPOINT_PATH = APP_DATA_DIR / "tracker_state.json"
FLUSH_REQUEST_PATH = APP_DATA_DIR / "tracker_flush.request"
FLUSH_ACK_PATH = APP_DATA_DIR / "tracker_flush.ack"

DEFAULT_CONFIG = {
    "poll_interval_s": 2.0,
    "max_session_s": 120.0,
    "idle_threshold_s": 300.0,
    "sleep_gap_s": 60.0,
    "user_id": None,
}


@dataclass
class TrackerConfig:
    poll_interval_s: float = 2.0
    max_session_s: float = 120.0
    idle_threshold_s: float = 300.0
    sleep_gap_s: float = 60.0
    user_id: int | None = None

    @classmethod
    def load(cls) -> TrackerConfig:
        APP_DATA_DIR.mkdir(parents=True, exist_ok=True)
        data = dict(DEFAULT_CONFIG)
        if CONFIG_PATH.exists():
            try:
                data.update(json.loads(CONFIG_PATH.read_text(encoding="utf-8")))
            except (json.JSONDecodeError, OSError) as exc:
                log.warning("Could not read tracker config: %s", exc)
        if os.environ.get("DESKTOP_POLL_INTERVAL"):
            data["poll_interval_s"] = float(os.environ["DESKTOP_POLL_INTERVAL"])
        if os.environ.get("DESKTOP_MAX_SESSION"):
            data["max_session_s"] = float(os.environ["DESKTOP_MAX_SESSION"])
        if os.environ.get("TRACKER_USER_ID"):
            data["user_id"] = int(os.environ["TRACKER_USER_ID"])
        uid = data.get("user_id")
        if uid is not None:
            uid = int(uid)
        return cls(
            poll_interval_s=float(data.get("poll_interval_s", 2.0)),
            max_session_s=float(data.get("max_session_s", 120.0)),
            idle_threshold_s=float(data.get("idle_threshold_s", 300.0)),
            sleep_gap_s=float(data.get("sleep_gap_s", 60.0)),
            user_id=uid,
        )

    def save(self) -> None:
        APP_DATA_DIR.mkdir(parents=True, exist_ok=True)
        CONFIG_PATH.write_text(json.dumps(asdict(self), indent=2), encoding="utf-8")


@dataclass
class SessionCheckpoint:
    last_poll_at: float = field(default_factory=time.time)
    current: dict[str, Any] | None = None

    @classmethod
    def load(cls) -> SessionCheckpoint | None:
        if not CHECKPOINT_PATH.exists():
            return None
        try:
            raw = json.loads(CHECKPOINT_PATH.read_text(encoding="utf-8"))
            return cls(
                last_poll_at=float(raw.get("last_poll_at", time.time())),
                current=raw.get("current"),
            )
        except (json.JSONDecodeError, OSError, TypeError, ValueError):
            return None

    def save(self) -> None:
        APP_DATA_DIR.mkdir(parents=True, exist_ok=True)
        CHECKPOINT_PATH.write_text(
            json.dumps({"last_poll_at": self.last_poll_at, "current": self.current}),
            encoding="utf-8",
        )

    def clear(self) -> None:
        if CHECKPOINT_PATH.exists():
            try:
                CHECKPOINT_PATH.unlink()
            except OSError:
                pass


def enable_sqlite_wal() -> None:
    from backend.db.sqlite_utils import configure_sqlite_engine

    configure_sqlite_engine(engine)
    try:
        with engine.connect() as conn:
            conn.execute(text("PRAGMA journal_mode=WAL"))
            conn.commit()
    except Exception as exc:  # noqa: BLE001
        log.debug("WAL pragma skipped: %s", exc)


def resolve_user_id(config: TrackerConfig) -> int:
    if config.user_id is not None:
        return config.user_id
    db = SessionLocal()
    try:
        from backend.models import User

        admin = db.query(User).filter(User.username == "admin").first()
        if admin:
            return admin.id
        user = ensure_demo_user(db)
        return user.id
    finally:
        db.close()


def resolve_username(user_id: int, *, db: Session | None = None) -> str:
    own = db is None
    session = db or SessionLocal()
    try:
        from backend.models import User

        row = session.query(User).filter(User.id == user_id).first()
        return row.username if row else f"user#{user_id}"
    finally:
        if own:
            session.close()


def tracker_log_path() -> Path:
    return LOGS_DIR / "desktop_tracker.log"


def launcher_log_path() -> Path:
    return LOGS_DIR / "tracker_launcher.log"


def append_launcher_log(mode: str, message: str) -> None:
    """Scripts call via small helper — records start/stop/errors."""
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    line = f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} [{mode}] {message}\n"
    try:
        with open(launcher_log_path(), "a", encoding="utf-8") as f:
            f.write(line)
    except OSError:
        pass


_CSV_FIELDS = [
    "type", "source", "exe", "title", "domain",
    "category", "productivity_score", "duration_seconds",
    "timestamp", "end_timestamp", "reason", "pid",
]


def append_csv_event(ev: dict) -> None:
    DATA_LOGS_DIR.mkdir(parents=True, exist_ok=True)
    day_str = datetime.now().strftime("%Y-%m-%d")
    csv_path = DATA_LOGS_DIR / f"DSC_desktop_behavior_{day_str}.csv"
    file_exists = csv_path.exists()
    with open(csv_path, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=_CSV_FIELDS, extrasaction="ignore")
        if not file_exists:
            writer.writeheader()
        writer.writerow(ev)


def persist_event(user_id: int, ev: dict, *, retries: int = 8) -> bool:
    """Write SESSION_END to SQLite (authoritative) and CSV backup."""
    append_csv_event(ev)
    for attempt in range(retries):
        db = SessionLocal()
        try:
            ingest_desktop_session(db, user_id=user_id, payload=ev)
            return True
        except OperationalError as exc:
            if "locked" in str(exc).lower() and attempt < retries - 1:
                time.sleep(0.15 * (attempt + 1))
                continue
            log.warning("SQLite write failed (attempt %s/%s): %s", attempt + 1, retries, exc)
            return False
        except Exception as exc:  # noqa: BLE001
            log.warning("Persist failed (attempt %s/%s): %s", attempt + 1, retries, exc)
            return False
        finally:
            db.close()
    return False


def today_total_seconds(user_id: int) -> int:
    """Sum tracked session duration for today (local date boundaries in UTC)."""
    today = date.today()
    start = datetime.combine(today, datetime.min.time()).replace(tzinfo=UTC)
    end = start + timedelta(days=1)
    db = SessionLocal()
    try:
        rows = (
            db.query(TrackedSession)
            .filter(
                TrackedSession.user_id == user_id,
                TrackedSession.source == "desktop_tracker",
                TrackedSession.start_time >= start,
                TrackedSession.start_time < end,
            )
            .all()
        )
        total = 0
        for row in rows:
            if row.start_time and row.end_time:
                total += max(0, int((row.end_time - row.start_time).total_seconds()))
        return total
    finally:
        db.close()


def last_event_at(user_id: int) -> datetime | None:
    db = SessionLocal()
    try:
        row = (
            db.query(func.max(TrackedSession.end_time))
            .filter(
                TrackedSession.user_id == user_id,
                TrackedSession.source == "desktop_tracker",
            )
            .scalar()
        )
        return row
    finally:
        db.close()


def request_tracker_flush() -> float:
    """Ask the standalone tracker process to flush its current session. Returns request timestamp."""
    APP_DATA_DIR.mkdir(parents=True, exist_ok=True)
    ts = time.time()
    FLUSH_REQUEST_PATH.write_text(str(ts), encoding="utf-8")
    if FLUSH_ACK_PATH.exists():
        try:
            FLUSH_ACK_PATH.unlink()
        except OSError:
            pass
    return ts


def write_flush_ack() -> None:
    APP_DATA_DIR.mkdir(parents=True, exist_ok=True)
    FLUSH_ACK_PATH.write_text(str(time.time()), encoding="utf-8")


def consume_flush_request() -> bool:
    if not FLUSH_REQUEST_PATH.exists():
        return False
    try:
        FLUSH_REQUEST_PATH.unlink()
        return True
    except OSError:
        return False


def wait_for_flush_ack(since_ts: float, *, timeout_s: float = 4.0) -> bool:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        if FLUSH_ACK_PATH.exists():
            try:
                ack_ts = float(FLUSH_ACK_PATH.read_text(encoding="utf-8").strip())
                if ack_ts >= since_ts - 0.5:
                    return True
            except (OSError, ValueError):
                pass
        time.sleep(0.15)
    return False


def setup_file_logging() -> None:
    """Append to data/logs/desktop_tracker.log when not running under pythonw-only."""
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    log_path = LOGS_DIR / "desktop_tracker.log"
    root = logging.getLogger("desktop_tracker")
    if any(isinstance(h, logging.FileHandler) for h in root.handlers):
        return
    fh = logging.FileHandler(log_path, encoding="utf-8")
    fh.setFormatter(logging.Formatter("%(asctime)s [desktop_tracker] %(message)s", datefmt="%H:%M:%S"))
    root.addHandler(fh)
