"""Map parse-speed slider to chunk/pause settings and show time/CPU estimates."""

from __future__ import annotations

import math
import sys
from dataclasses import dataclass


@dataclass(frozen=True)
class ParseThrottle:
    """speed 0 = fast (hotter CPU), 100 = slow (cooler CPU)."""

    speed: int = 50
    chunk_lines: int = 350
    pause_ms: float = 20.0


def clamp_speed(speed: int) -> int:
    return max(0, min(100, int(speed)))


def speed_to_throttle(speed: int) -> ParseThrottle:
    """Convert UI slider 0–100 into chunk size and pause between batches."""
    s = clamp_speed(speed) / 100.0
    chunk_lines = int(520 - s * 370)  # 520 lines @ fast → 150 @ slow
    pause_ms = 1.0 + s * 99.0  # 1 ms → 100 ms between chunks
    return ParseThrottle(speed=clamp_speed(speed), chunk_lines=max(80, chunk_lines), pause_ms=pause_ms)


def throttle_labels(speed: int) -> tuple[str, str]:
    s = clamp_speed(speed)
    if s <= 20:
        pace = "Fast"
    elif s <= 45:
        pace = "Balanced"
    elif s <= 70:
        pace = "Cool"
    else:
        pace = "Very cool"
    return pace, f"{s}% throttle"


def estimate_parse_seconds(
    line_count: int,
    speed: int,
    *,
    thorough: bool,
    aggressive: bool = False,
) -> float:
    """Rough wall-clock estimate before parsing starts."""
    lines = max(1, line_count)
    if not thorough or lines < 80:
        return max(0.3, lines * 0.00008)

    t = speed_to_throttle(speed)
    chunks = max(1, math.ceil(lines / t.chunk_lines))
    pause_sec = t.pause_ms / 1000.0
    work_per_chunk = 0.012 + (0.004 if aggressive else 0.0)

    # pass 1: per-chunk work + pause
    pass1 = chunks * (work_per_chunk + pause_sec)
    # passes 2–4: global dedup + short pauses
    pass_rest = 0.25 + lines * 0.00004 + (2.0 * pause_sec)
    return pass1 + pass_rest


def format_eta(seconds: float) -> str:
    if seconds < 1.5:
        return "~1 sec"
    if seconds < 90:
        return f"~{int(round(seconds))} sec"
    minutes = int(seconds // 60)
    secs = int(round(seconds % 60))
    return f"~{minutes}m {secs}s" if secs else f"~{minutes} min"


def estimate_cpu_load_pct(speed: int, *, thorough: bool) -> int:
    """Estimated average CPU use during parse (not a live reading)."""
    s = clamp_speed(speed)
    if not thorough:
        return max(20, 55 - s // 3)
    # fast ≈ 80%, slow ≈ 25%
    return int(max(18, min(88, 82 - s * 0.58)))


def load_label(load_pct: int) -> str:
    if load_pct >= 70:
        return "High"
    if load_pct >= 45:
        return "Moderate"
    return "Light"


def try_cpu_temp_celsius() -> float | None:
    """Best-effort live CPU temperature; None if unavailable on this PC."""
    try:
        from transcript_studio.system_sensors import try_cpu_temp_celsius as _read

        return _read()
    except Exception:
        return None


def format_temp_line(temp_c: float | None, *, load_pct: int) -> str:
    if temp_c is not None:
        return f"CPU now: {temp_c:.0f}°C"
    cooler = "slower slider = less heat" if load_pct >= 50 else "load should stay moderate"
    return f"CPU temp: n/a ({cooler})"


def format_parse_estimate(
    line_count: int,
    speed: int,
    *,
    thorough: bool,
    aggressive: bool = False,
    temp_c: float | None = None,
) -> str:
    eta_sec = estimate_parse_seconds(line_count, speed, thorough=thorough, aggressive=aggressive)
    load = estimate_cpu_load_pct(speed, thorough=thorough)
    pace, _ = throttle_labels(speed)
    t = speed_to_throttle(speed)
    return (
        f"Est. {format_eta(eta_sec)} · {pace} · "
        f"~{load}% CPU ({load_label(load)}) · "
        f"chunk {t.chunk_lines} lines / {t.pause_ms:.0f} ms pause · "
        f"{format_temp_line(temp_c, load_pct=load)}"
    )
