"""Multi-pass, chunked transcript parse — spreads CPU load, improves dedup accuracy."""

from __future__ import annotations

import time
from typing import Callable

from transcript_studio.cleanup import (
    FILLER_RE,
    STUTTER_RE,
    WHITESPACE_RE,
    aggressive_prefix_dedup,
    clean_transcript,
    dedupe_lines,
    maximal_prefix_dedup,
    normalize_segment,
)

ProgressFn = Callable[[str, float], None]
CancelFn = Callable[[], bool]


def _report(on_progress: ProgressFn | None, msg: str, fraction: float) -> None:
    if on_progress:
        on_progress(msg, max(0.0, min(1.0, fraction)))


def _sleep_pause(pause_sec: float) -> None:
    if pause_sec > 0:
        time.sleep(pause_sec)


def parse_transcript_chunked(
    raw: str,
    *,
    aggressive: bool = False,
    chunk_lines: int = 350,
    pause_sec: float = 0.02,
    multi_pass: bool = True,
    on_progress: ProgressFn | None = None,
    cancel_event: CancelFn | None = None,
) -> str:
    """
    Parse in batches with optional pauses between chunks (keeps CPU cooler).

    Pass 1 — normalize lines in chunks
    Pass 2 — global line dedup (standard or aggressive)
    Pass 3 — (optional) second dedup pass for aggressive mode
    Pass 4 — filler / stutter cleanup on joined text
    """
    chunk_lines = max(50, int(chunk_lines))
    lines_in = raw.splitlines()
    total_in = max(1, len(lines_in))
    normalized: list[str] = []

    _report(on_progress, "Pass 1/4: normalizing lines…", 0.02)
    for start in range(0, len(lines_in), chunk_lines):
        if cancel_event and cancel_event():
            raise RuntimeError("Parse cancelled")
        batch = lines_in[start : start + chunk_lines]
        for ln in batch:
            seg = normalize_segment(ln)
            if seg:
                normalized.append(seg)
        end = min(start + chunk_lines, total_in)
        frac = 0.05 + 0.35 * (end / total_in)
        _report(on_progress, f"Pass 1/4: normalized {end:,}/{total_in:,} lines", frac)
        _sleep_pause(pause_sec)

    if not normalized:
        return ""

    _report(on_progress, "Pass 2/4: deduplicating lines…", 0.45)
    if cancel_event and cancel_event():
        raise RuntimeError("Parse cancelled")
    if aggressive:
        kept = maximal_prefix_dedup(normalized)
    else:
        kept = dedupe_lines(normalized)

    if multi_pass and aggressive and len(kept) > 1:
        _report(on_progress, "Pass 3/4: second dedup pass…", 0.62)
        _sleep_pause(pause_sec)
        if cancel_event and cancel_event():
            raise RuntimeError("Parse cancelled")
        kept = aggressive_prefix_dedup(kept)
        kept = dedupe_lines(kept)
    elif multi_pass:
        _report(on_progress, "Pass 3/4: tightening duplicates…", 0.62)
        _sleep_pause(pause_sec)
        kept = dedupe_lines(kept)

    _report(on_progress, "Pass 4/4: filler and stutter cleanup…", 0.82)
    text = " ".join(kept)
    text = FILLER_RE.sub(" ", text)
    text = STUTTER_RE.sub(r"\1", text)
    text = WHITESPACE_RE.sub(" ", text).strip()

    _report(on_progress, "Parse complete", 1.0)
    return text


def parse_transcript_auto(
    raw: str,
    *,
    aggressive: bool = False,
    thorough: bool = True,
    chunk_lines: int = 350,
    pause_sec: float = 0.02,
    on_progress: ProgressFn | None = None,
    cancel_event: CancelFn | None = None,
) -> str:
    """Use chunked multi-pass parse when thorough=True, else fast single-pass."""
    if thorough and len(raw.splitlines()) >= 80:
        return parse_transcript_chunked(
            raw,
            aggressive=aggressive,
            chunk_lines=chunk_lines,
            pause_sec=pause_sec,
            multi_pass=True,
            on_progress=on_progress,
            cancel_event=cancel_event,
        )
    if on_progress:
        on_progress("Fast parse…", 0.5)
    result = clean_transcript(raw, aggressive=aggressive)
    if on_progress:
        on_progress("Parse complete", 1.0)
    return result
