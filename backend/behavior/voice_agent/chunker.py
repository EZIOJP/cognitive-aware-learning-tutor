"""Sentence stream chunker — pure CPU, no GPU deps.

Feeds incremental LLM tokens and emits complete sentences for TTS.
"""

from __future__ import annotations

_TERMINATORS = frozenset(".!?…")
_TRAILING_CLOSE = frozenset("\"'”’)]]}")


class SentenceStreamChunker:
    """Accumulate streamed text; yield sentences as they complete."""

    def __init__(self, *, min_chars: int = 8) -> None:
        self.min_chars = max(1, int(min_chars))
        self._buf = ""

    def feed(self, text: str) -> list[str]:
        """Append token text; return any newly completed sentences."""
        if not text:
            return []
        self._buf += text
        return self._extract(final=False)

    def flush(self) -> list[str]:
        """Emit remaining buffer as a final chunk (if non-empty)."""
        out = self._extract(final=True)
        tail = self._buf.strip()
        if tail:
            out.append(tail)
        self._buf = ""
        return out

    def reset(self) -> None:
        self._buf = ""

    @property
    def buffer(self) -> str:
        return self._buf

    def _extract(self, *, final: bool) -> list[str]:
        out: list[str] = []
        while self._buf:
            cut = self._find_sentence_end(final=final)
            if cut is None:
                break
            sent = self._buf[:cut].strip()
            self._buf = self._buf[cut:]
            if sent:
                out.append(sent)
        return out

    def _find_sentence_end(self, *, final: bool) -> int | None:
        """Return index after sentence (+ trailing whitespace), or None if incomplete."""
        i = 0
        n = len(self._buf)
        while i < n:
            ch = self._buf[i]
            if ch not in _TERMINATORS:
                i += 1
                continue
            # Decimal / version: digit . digit
            if (
                ch == "."
                and i > 0
                and self._buf[i - 1].isdigit()
                and i + 1 < n
                and self._buf[i + 1].isdigit()
            ):
                i += 1
                continue
            j = i + 1
            while j < n and self._buf[j] in _TRAILING_CLOSE:
                j += 1
            if j < n:
                if self._buf[j].isspace():
                    while j < n and self._buf[j].isspace():
                        j += 1
                    sent = self._buf[:j].strip()
                    if len(sent) >= self.min_chars or final:
                        return j
                    # Very short sentence with more text — still emit
                    return j
                i = j
                continue
            # Terminator at end of buffer
            if final:
                return n
            return None
        return None
