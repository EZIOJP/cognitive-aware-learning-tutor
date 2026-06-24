"""FSRS-inspired spaced repetition for all quiz domains.

Lightweight scheduler (no external FSRS dependency): stability + difficulty
with interval growth on success and rapid re-queue on lapse.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta


@dataclass
class SrsState:
    mastery: int = 0
    ease: float = 2.5
    stability: float = 0.4
    difficulty: float = 5.0
    interval_days: int = 0
    due_date: datetime | None = None
    times_asked: int = 0
    times_correct: int = 0
    consecutive_correct: int = 0
    lapses: int = 0


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def calc_interval_days(state: SrsState) -> int:
    """Days until next review from stability and difficulty."""
    if state.stability < 0.5:
        return 1
    base = state.stability * (11.0 - state.difficulty) / 10.0
    return max(1, int(round(_clamp(base, 1.0, 180.0))))


def schedule_after_answer(
    state: SrsState,
    *,
    correct: bool,
    elapsed_ms: int = 0,
) -> SrsState:
    """Update card state after one graded attempt."""
    state.times_asked += 1
    now = datetime.now(UTC)

    if correct:
        state.times_correct += 1
        state.consecutive_correct += 1
        state.mastery = min(10, state.mastery + 1)
        state.ease = min(3.0, state.ease + 0.08)
        state.difficulty = _clamp(state.difficulty - 0.15, 1.0, 10.0)

        if state.consecutive_correct <= 1:
            state.stability = 1.0
        else:
            growth = state.ease * (1.0 + math.log1p(state.stability))
            if elapsed_ms > 45_000:
                growth *= 0.92
            state.stability = _clamp(state.stability + growth, 0.5, 120.0)
    else:
        state.consecutive_correct = 0
        state.mastery = max(-2, state.mastery - 2)
        state.lapses += 1
        state.ease = max(1.3, state.ease - 0.25)
        state.difficulty = _clamp(state.difficulty + 0.8, 1.0, 10.0)
        state.stability = max(0.4, state.stability * 0.35)

    state.interval_days = calc_interval_days(state)
    state.due_date = now + timedelta(days=state.interval_days)
    return state


def is_due(state: SrsState, *, now: datetime | None = None) -> bool:
    now = now or datetime.now(UTC)
    if state.due_date is None:
        return state.mastery < 3 or state.times_asked == 0
    return now >= state.due_date.replace(tzinfo=UTC) if state.due_date.tzinfo is None else now >= state.due_date.astimezone(UTC)


def srs_from_metadata(raw: dict | None) -> SrsState:
    if not raw:
        return SrsState()
    due_raw = raw.get("due_date")
    due = None
    if due_raw:
        due = datetime.fromisoformat(str(due_raw).replace("Z", "+00:00")).astimezone(UTC)
    return SrsState(
        mastery=int(raw.get("mastery", 0)),
        ease=float(raw.get("ease", 2.5)),
        stability=float(raw.get("stability", 0.4)),
        difficulty=float(raw.get("difficulty", 5.0)),
        interval_days=int(raw.get("interval_days", 0)),
        due_date=due,
        times_asked=int(raw.get("times_asked", 0)),
        times_correct=int(raw.get("times_correct", 0)),
        consecutive_correct=int(raw.get("consecutive_correct", 0)),
        lapses=int(raw.get("lapses", 0)),
    )


def srs_to_metadata(state: SrsState) -> dict:
    return {
        "mastery": state.mastery,
        "ease": round(state.ease, 2),
        "stability": round(state.stability, 2),
        "difficulty": round(state.difficulty, 2),
        "interval_days": state.interval_days,
        "due_date": state.due_date.astimezone(UTC).isoformat().replace("+00:00", "Z")
        if state.due_date
        else None,
        "times_asked": state.times_asked,
        "times_correct": state.times_correct,
        "consecutive_correct": state.consecutive_correct,
        "lapses": state.lapses,
    }
