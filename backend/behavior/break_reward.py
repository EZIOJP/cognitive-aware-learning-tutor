"""Incubation breaks + earned free-time ledger (Desktop Tracker v2c).

§0 defaults (Q6/Q7):
- work 45 min → break 8 min; max 1 incubation / hour; no snooze
- Bible +15, plan confirm +10, daily goal +30; daily earn cap 60
- Q4 D1: PIN cannot free-override while incubation active
- Q5 E1: spend → set_free_override + ledger debit
- Q3 C2: force study-hard during incubation
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from backend.paths import ROOT

CONFIG_PATH = ROOT / "data" / "behavior" / "break_reward_config.json"

KIND_INCUBATION = "incubation"
KIND_EARNED = "earned"

REASON_BIBLE = "bible_done"
REASON_PLAN = "plan_confirm"
REASON_DAILY_GOAL = "daily_goal"
REASON_SPEND = "spend_free"

DEFAULT_CONFIG: dict[str, Any] = {
    "work_minutes": 45,
    "break_minutes": 8,
    "max_incubations_per_hour": 1,
    "allow_snooze": False,
    "earn": {
        REASON_BIBLE: 15,
        REASON_PLAN: 10,
        REASON_DAILY_GOAL: 30,
    },
    "daily_earn_cap": 60,
}


class IncubationBlocksFreeOverride(ValueError):
    """Raised when PIN / free override is denied during an active incubation."""

    def __init__(self, message: str = "PIN free override blocked during incubation break") -> None:
        super().__init__(message)


def _utc_now(now: datetime | None = None) -> datetime:
    dt = now if now is not None else datetime.now(UTC)
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def _as_aware_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def _session(db: Session | None) -> tuple[Session, bool]:
    if db is not None:
        return db, False
    from backend.db.base import SessionLocal

    return SessionLocal(), True


def load_config(*, path: Path | None = None, write_defaults: bool = True) -> dict[str, Any]:
    """Load break/reward config; write Q6/Q7 defaults if the file is missing."""
    store = path if path is not None else CONFIG_PATH
    if store.is_file():
        try:
            raw = json.loads(store.read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                return _merge_defaults(raw)
        except (OSError, json.JSONDecodeError, TypeError, ValueError):
            pass
    cfg = dict(DEFAULT_CONFIG)
    cfg["earn"] = dict(DEFAULT_CONFIG["earn"])
    if write_defaults:
        try:
            store.parent.mkdir(parents=True, exist_ok=True)
            store.write_text(json.dumps(cfg, indent=2) + "\n", encoding="utf-8")
        except OSError:
            pass
    return cfg


def _merge_defaults(raw: dict[str, Any]) -> dict[str, Any]:
    out = dict(DEFAULT_CONFIG)
    out["earn"] = dict(DEFAULT_CONFIG["earn"])
    for key in ("work_minutes", "break_minutes", "max_incubations_per_hour", "allow_snooze", "daily_earn_cap"):
        if key in raw:
            out[key] = raw[key]
    earn = raw.get("earn")
    if isinstance(earn, dict):
        for k, v in earn.items():
            try:
                out["earn"][str(k)] = int(v)
            except (TypeError, ValueError):
                continue
    try:
        out["work_minutes"] = max(1, int(out["work_minutes"]))
        out["break_minutes"] = max(1, int(out["break_minutes"]))
        out["max_incubations_per_hour"] = max(0, int(out["max_incubations_per_hour"]))
        out["daily_earn_cap"] = max(0, int(out["daily_earn_cap"]))
        out["allow_snooze"] = bool(out["allow_snooze"])
    except (TypeError, ValueError):
        return dict(DEFAULT_CONFIG)
    return out


def balance(user_id: int, *, db: Session | None = None) -> int:
    """Current ledger balance (0 when empty)."""
    from backend.models.break_reward import RewardLedger

    session, own = _session(db)
    try:
        row = (
            session.query(RewardLedger)
            .filter(RewardLedger.user_id == int(user_id))
            .order_by(RewardLedger.id.desc())
            .first()
        )
        return int(row.balance_after) if row is not None else 0
    finally:
        if own:
            session.close()


def daily_earned(user_id: int, *, db: Session | None = None, now: datetime | None = None) -> int:
    """Sum of positive earn deltas for the local calendar day."""
    from backend.models.break_reward import RewardLedger
    from backend.planner.service import local_tz

    dt = now if now is not None else datetime.now(local_tz())
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=local_tz())
    else:
        dt = dt.astimezone(local_tz())
    day_start = datetime(dt.year, dt.month, dt.day, tzinfo=local_tz()).astimezone(UTC)
    day_end = day_start + timedelta(days=1)

    session, own = _session(db)
    try:
        rows = (
            session.query(RewardLedger)
            .filter(RewardLedger.user_id == int(user_id), RewardLedger.delta_minutes > 0)
            .all()
        )
        total = 0
        for row in rows:
            created = _as_aware_utc(row.created_at)
            if day_start <= created < day_end:
                total += max(0, int(row.delta_minutes))
        return total
    finally:
        if own:
            session.close()


def earn(
    user_id: int,
    reason: str,
    minutes: int | None = None,
    *,
    ref_id: str | None = None,
    db: Session | None = None,
    now: datetime | None = None,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Credit earned free minutes (respects daily cap). Returns ledger summary."""
    from backend.models.break_reward import RewardLedger

    cfg = config if config is not None else load_config()
    reason_key = str(reason or "").strip()
    if not reason_key:
        raise ValueError("reason required")

    if minutes is None:
        earn_map = cfg.get("earn") if isinstance(cfg.get("earn"), dict) else {}
        try:
            minutes = int(earn_map.get(reason_key) or 0)
        except (TypeError, ValueError):
            minutes = 0
    delta = int(minutes)
    if delta <= 0:
        return {
            "credited": 0,
            "balance": balance(user_id, db=db),
            "daily_earned": daily_earned(user_id, db=db, now=now),
            "daily_cap": int(cfg.get("daily_earn_cap") or 0),
            "reason": reason_key,
        }

    cap = max(0, int(cfg.get("daily_earn_cap") or 0))
    session, own = _session(db)
    try:
        already = daily_earned(int(user_id), db=session, now=now)
        remaining_cap = max(0, cap - already) if cap else delta
        credited = min(delta, remaining_cap)
        bal = balance(int(user_id), db=session)
        if credited <= 0:
            return {
                "credited": 0,
                "balance": bal,
                "daily_earned": already,
                "daily_cap": cap,
                "reason": reason_key,
                "capped": True,
            }

        new_bal = bal + credited
        row = RewardLedger(
            user_id=int(user_id),
            delta_minutes=credited,
            reason=reason_key,
            created_at=_utc_now(now).replace(tzinfo=None),
            ref_id=ref_id,
            balance_after=new_bal,
        )
        session.add(row)
        session.commit()
        return {
            "credited": credited,
            "balance": new_bal,
            "daily_earned": already + credited,
            "daily_cap": cap,
            "reason": reason_key,
            "capped": credited < delta,
        }
    except Exception:
        session.rollback()
        raise
    finally:
        if own:
            session.close()


def spend(
    user_id: int,
    minutes: int,
    *,
    db: Session | None = None,
    now: datetime | None = None,
    apply_override: bool = True,
) -> dict[str, Any]:
    """Debit ledger and (Q5 E1) call set_free_override. Blocked during incubation."""
    from backend.models.break_reward import RewardLedger

    mins = int(minutes)
    if mins <= 0:
        raise ValueError("minutes must be positive")

    session, own = _session(db)
    try:
        tick_incubation(int(user_id), db=session, now=now)
        if incubation_active(int(user_id), db=session, now=now):
            raise IncubationBlocksFreeOverride()

        bal = balance(int(user_id), db=session)
        if mins > bal:
            raise ValueError(f"insufficient_balance: have {bal}, need {mins}")

        new_bal = bal - mins
        row = RewardLedger(
            user_id=int(user_id),
            delta_minutes=-mins,
            reason=REASON_SPEND,
            created_at=_utc_now(now).replace(tzinfo=None),
            ref_id=None,
            balance_after=new_bal,
        )
        session.add(row)
        session.commit()

        if apply_override:
            from backend.behavior.browser_gate_policy import set_free_override

            # Already verified not incubating; skip re-check to avoid solo-owner DB hop.
            try:
                set_free_override(minutes=mins, now=now, skip_incubation_check=True)
            except Exception:
                # Reverse debit if override could not be applied.
                session.add(
                    RewardLedger(
                        user_id=int(user_id),
                        delta_minutes=mins,
                        reason="spend_rollback",
                        created_at=_utc_now(now).replace(tzinfo=None),
                        ref_id=None,
                        balance_after=bal,
                    )
                )
                session.commit()
                raise

        return {
            "spent": mins,
            "balance": new_bal,
            "reason": REASON_SPEND,
        }
    except Exception:
        session.rollback()
        raise
    finally:
        if own:
            session.close()


def _open_incubation(session: Session, user_id: int):
    from backend.models.break_reward import BreakSession

    return (
        session.query(BreakSession)
        .filter(
            BreakSession.user_id == int(user_id),
            BreakSession.kind == KIND_INCUBATION,
            BreakSession.ended_at.is_(None),
        )
        .order_by(BreakSession.id.desc())
        .first()
    )


def _incubation_remaining(row, now: datetime) -> int:
    started = _as_aware_utc(row.started_at)
    end = started + timedelta(seconds=max(0, int(row.duration_sec)))
    rem = int((end - _as_aware_utc(now)).total_seconds())
    return max(0, rem)


def _close_expired_incubations(session: Session, user_id: int, now: datetime) -> None:
    from backend.models.break_reward import BreakSession

    open_rows = (
        session.query(BreakSession)
        .filter(
            BreakSession.user_id == int(user_id),
            BreakSession.kind == KIND_INCUBATION,
            BreakSession.ended_at.is_(None),
        )
        .all()
    )
    changed = False
    for row in open_rows:
        if _incubation_remaining(row, now) <= 0:
            row.ended_at = now.replace(tzinfo=None)
            changed = True
    if changed:
        session.commit()


def _status_from_db(
    session: Session,
    user_id: int,
    now: datetime,
    *,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    cfg = config if config is not None else load_config()
    default_total = max(1, int(cfg.get("break_minutes") or 8)) * 60
    row = _open_incubation(session, int(user_id))
    if row is None:
        return {"active": False, "remaining_sec": 0, "total_sec": default_total}
    rem = _incubation_remaining(row, now)
    total = max(1, int(row.duration_sec))
    return {"active": rem > 0, "remaining_sec": rem, "total_sec": total}


def incubation_active(user_id: int, *, db: Session | None = None, now: datetime | None = None) -> bool:
    """True when an open incubation session still has remaining time."""
    session, own = _session(db)
    try:
        dt = _utc_now(now)
        _close_expired_incubations(session, int(user_id), dt)
        return _status_from_db(session, int(user_id), dt)["active"]
    finally:
        if own:
            session.close()


def force_study_hard(user_id: int, *, db: Session | None = None, now: datetime | None = None) -> bool:
    """Q3 C2 — enforcer / gate should force study mode while incubation is active."""
    return incubation_active(user_id, db=db, now=now)


def incubation_status(
    user_id: int,
    *,
    db: Session | None = None,
    now: datetime | None = None,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    session, own = _session(db)
    try:
        dt = _utc_now(now)
        _close_expired_incubations(session, int(user_id), dt)
        return _status_from_db(session, int(user_id), dt, config=config)
    finally:
        if own:
            session.close()


def start_incubation(
    user_id: int,
    *,
    source_session_id: str | None = None,
    db: Session | None = None,
    now: datetime | None = None,
    config: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    """Start a mandatory incubation break. Returns status or None if refused (rate limit)."""
    from backend.models.break_reward import BreakSession

    cfg = config if config is not None else load_config()
    break_sec = max(1, int(cfg.get("break_minutes") or 8)) * 60
    max_per_hour = max(0, int(cfg.get("max_incubations_per_hour") or 0))
    dt = _utc_now(now)

    session, own = _session(db)
    try:
        _close_expired_incubations(session, int(user_id), dt)
        existing = _open_incubation(session, int(user_id))
        if existing is not None and _incubation_remaining(existing, dt) > 0:
            return _status_from_db(session, int(user_id), dt, config=cfg)

        if max_per_hour > 0:
            hour_ago = (dt - timedelta(hours=1)).replace(tzinfo=None)
            recent = (
                session.query(BreakSession)
                .filter(
                    BreakSession.user_id == int(user_id),
                    BreakSession.kind == KIND_INCUBATION,
                    BreakSession.started_at >= hour_ago,
                )
                .count()
            )
            if recent >= max_per_hour:
                return None

        row = BreakSession(
            user_id=int(user_id),
            kind=KIND_INCUBATION,
            started_at=dt.replace(tzinfo=None),
            duration_sec=break_sec,
            ended_at=None,
            source_session_id=source_session_id,
            payload_json="{}",
        )
        session.add(row)
        session.commit()
        return {
            "active": True,
            "remaining_sec": break_sec,
            "total_sec": break_sec,
            "session_id": int(row.id),
        }
    except Exception:
        session.rollback()
        raise
    finally:
        if own:
            session.close()


def tick_incubation(
    user_id: int,
    *,
    db: Session | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Close expired open incubations; return current status."""
    session, own = _session(db)
    try:
        dt = _utc_now(now)
        _close_expired_incubations(session, int(user_id), dt)
        return _status_from_db(session, int(user_id), dt)
    finally:
        if own:
            session.close()


def solo_incubation_active(*, db: Session | None = None, now: datetime | None = None) -> bool:
    """Incubation check for file-based gate helpers (no user_id in signature)."""
    try:
        from backend.core.auth import ensure_solo_owner

        session, own = _session(db)
        try:
            user = ensure_solo_owner(session)
            return incubation_active(int(user.id), db=session, now=now)
        finally:
            if own:
                session.close()
    except Exception:
        return False
