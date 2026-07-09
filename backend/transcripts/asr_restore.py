"""Automatic punctuation and case restoration for unpunctuated ASR transcripts."""

from __future__ import annotations

import logging
import re
import time

log = logging.getLogger(__name__)

_RECASEPUNC_PREDICTOR: object | None = None
_FULLSTOP_MODEL: object | None = None

_CAP_AFTER_PERIOD_RE = re.compile(r"([.!?]\s+)([a-z])")


def is_available(*, backend: str = "recasepunc") -> bool:
    key = (backend or "recasepunc").strip().lower()
    if key in ("fullstop", "deepmultilingual"):
        try:
            from deepmultilingualpunctuation import PunctuationModel  # noqa: F401

            return True
        except ImportError:
            return False
    try:
        from recasepunc import CasePuncPredictor  # noqa: F401

        return True
    except ImportError:
        return False


def _restore_recasepunc(text: str) -> str:
    global _RECASEPUNC_PREDICTOR
    try:
        from recasepunc import CasePuncPredictor, WordpieceTokenizer
    except ImportError:
        log.warning("recasepunc not installed — skipping ASR punctuation restore")
        return text

    if _RECASEPUNC_PREDICTOR is None:
        log.info("Loading recasepunc models (first use may download weights)…")
        _RECASEPUNC_PREDICTOR = CasePuncPredictor(
            "cases_en.lstm.annonced",
            "subwords_en.lstm.annonced",
        )

    lines_out: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or len(stripped.split()) < 4:
            lines_out.append(line)
            continue
        tokens = WordpieceTokenizer(list(stripped), True)
        if not tokens:
            lines_out.append(line)
            continue
        cased = _RECASEPUNC_PREDICTOR.predict_tokenized(tokens)  # type: ignore[union-attr]
        restored = " ".join(
            f"{word}{punct or ''}" for word, punct in cased
        ).strip()
        lines_out.append(restored if restored else line)
    return "\n".join(lines_out)


def _restore_fullstop(text: str) -> str:
    global _FULLSTOP_MODEL
    try:
        from deepmultilingualpunctuation import PunctuationModel
    except ImportError:
        log.warning("deepmultilingualpunctuation not installed — falling back to recasepunc")
        return _restore_recasepunc(text)

    if _FULLSTOP_MODEL is None:
        log.info("Loading FullStop punctuation model…")
        _FULLSTOP_MODEL = PunctuationModel(model="oliverguhr/fullstop-punctuation-multilang-large")

    try:
        return str(_FULLSTOP_MODEL.restore_punctuation(text))  # type: ignore[union-attr]
    except Exception as exc:  # noqa: BLE001
        log.warning("FullStop restore failed: %s — returning original text", exc)
        return text


def _heuristic_restore(text: str) -> str:
    """Minimal fallback when ML models are unavailable."""
    out_lines: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            out_lines.append("")
            continue
        if stripped[-1] not in ".!?":
            stripped = stripped + "."
        if stripped and stripped[0].islower():
            stripped = stripped[0].upper() + stripped[1:]
        stripped = _CAP_AFTER_PERIOD_RE.sub(lambda m: m.group(1) + m.group(2).upper(), stripped)
        out_lines.append(stripped)
    return "\n".join(out_lines)


def restore_punctuation(
    text: str,
    *,
    backend: str = "recasepunc",
) -> str:
    """Restore punctuation and casing on unpunctuated ASR text."""
    if not text or not text.strip():
        return text
    key = (backend or "recasepunc").strip().lower()
    if key in ("fullstop", "deepmultilingual"):
        if is_available(backend="fullstop"):
            return _restore_fullstop(text)
        return _heuristic_restore(text)
    if is_available(backend="recasepunc"):
        return _restore_recasepunc(text)
    return _heuristic_restore(text)


def maybe_restore_asr(
    cleaned: str,
    raw: str,
    *,
    enabled: bool = False,
    auto_for_live_captions: bool = True,
    backend: str = "recasepunc",
) -> str:
    """Apply ASR restore when enabled or when transcript looks like live captions."""
    from backend.transcripts.cleanup import looks_like_live_captions

    should = bool(enabled) or (auto_for_live_captions and looks_like_live_captions(raw))
    if not should:
        return cleaned
    from backend.transcripts._debug_agent_log import agent_log

    agent_log(
        location="asr_restore.py:maybe_restore_asr",
        message="asr_start",
        data={"enabled": enabled, "backend": backend, "chars": len(cleaned), "lines": cleaned.count("\n") + 1},
        hypothesis_id="H2",
    )
    t0 = time.perf_counter()
    log.info("ASR punctuation restore (%s)…", backend)
    out = restore_punctuation(cleaned, backend=backend)
    agent_log(
        location="asr_restore.py:maybe_restore_asr",
        message="asr_done",
        data={"elapsed_ms": int((time.perf_counter() - t0) * 1000), "out_chars": len(out)},
        hypothesis_id="H2",
    )
    return out
