"""Live-caption sentence stability + better-version replace.

Borrowed ideas from SaveLiveCaptions (MIT): wait until a sentence is stable
across several polls, replace near-duplicates with a longer/clearer revision,
then optional post-pass similarity cleanup. Keeps CALT attach/seed/idle stack.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from typing import Literal

CommitAction = Literal["append", "replace_last"]

_INCOMPLETE_END_RE = re.compile(r"[,，;；:\-–—]$")
_HAS_TERMINAL_RE = re.compile(r"[.!?。！？]")
_TIMESTAMP_PREFIX_RE = re.compile(r"^\[\d{2}:\d{2}:\d{2}\]\s*")


def strip_caption_timestamp(line: str) -> str:
    """Remove optional ``[HH:MM:SS]`` prefix from a saved caption line."""
    return _TIMESTAMP_PREFIX_RE.sub("", (line or "").strip()).strip()


def normalize_for_compare(s: str) -> str:
    s = strip_caption_timestamp(s)
    s = re.sub(r"\s+", " ", s.strip().lower())
    s = re.sub(r"\s+([.,!?])", r"\1", s)
    return s


def similarity_ratio(a: str, b: str) -> float:
    return SequenceMatcher(None, normalize_for_compare(a), normalize_for_compare(b)).ratio()


def is_better_version(new: str, old: str, *, near_equal: float = 0.95) -> bool:
    """True when ``new`` is a clearer/longer revision of ``old`` (SaveLC-style)."""
    new_s, old_s = new.strip(), old.strip()
    if not new_s or not old_s:
        return bool(new_s and not old_s)
    if similarity_ratio(new_s, old_s) >= near_equal:
        return False
    new_nums = len(re.findall(r"\d+\.?\d*", new_s))
    old_nums = len(re.findall(r"\d+\.?\d*", old_s))
    if new_nums > old_nums:
        return True
    new_words = len(re.findall(r"\b\w+\b", new_s))
    old_words = len(re.findall(r"\b\w+\b", old_s))
    if new_words > old_words + 2:
        return True
    if len(new_s) > len(old_s) * 1.2:
        return True
    new_punct = len(re.findall(r"[.!?，。！？,]", new_s))
    old_punct = len(re.findall(r"[.!?，。！？,]", old_s))
    return new_punct > old_punct


def is_incomplete_sentence(s: str) -> bool:
    s = s.strip()
    if not s or len(s) < 2:
        return True
    if _INCOMPLETE_END_RE.search(s):
        return True
    # No terminal punctuation yet → still growing in the LC panel.
    if not _HAS_TERMINAL_RE.search(s):
        return True
    # Ends with terminal → treat as complete enough to stabilize.
    return False


def split_caption_sentences(text: str) -> list[str]:
    text = re.sub(r"\s+", " ", (text or "").strip())
    if not text:
        return []
    parts = [p.strip() for p in re.split(r"(?<=[.!?。！？;；])\s+", text) if p and p.strip()]
    return parts or [text]


@dataclass
class CaptionStabilizer:
    """Hold LC panel sentences until they look finished and stable."""

    stable_threshold: int = 3
    min_length: int = 10
    similarity: float = 0.85
    _counts: dict[str, int] = field(default_factory=dict)
    _seen: set[str] = field(default_factory=set)

    def mark_seen_from_panel(self, panel_text: str) -> None:
        """Seed: existing panel text must not flush into the transcript."""
        for sentence in split_caption_sentences(panel_text):
            if not is_incomplete_sentence(sentence) and len(sentence) >= self.min_length:
                self._seen.add(normalize_for_compare(sentence))
                self._counts.pop(sentence, None)

    def observe_panel(self, panel_text: str) -> list[tuple[CommitAction, str]]:
        """
        Observe full Live Captions panel text.

        Returns commits as ``("append"|"replace_last", sentence)``.
        """
        sentences = split_caption_sentences(panel_text)
        frame_complete = [
            s
            for s in sentences
            if not is_incomplete_sentence(s) and len(s.strip()) >= self.min_length
        ]
        frame_set = set(frame_complete)
        next_counts: dict[str, int] = {}
        commits: list[tuple[CommitAction, str]] = []

        for sentence in frame_complete:
            key = normalize_for_compare(sentence)
            if key in self._seen:
                continue

            # Prefer longer revision of an already-seen near-duplicate.
            replaced_seen = False
            for seen_key in list(self._seen):
                if similarity_ratio(sentence, seen_key) < self.similarity:
                    continue
                if is_better_version(sentence, seen_key):
                    self._seen.discard(seen_key)
                    self._seen.add(key)
                    commits.append(("replace_last", sentence))
                    replaced_seen = True
                    break
                replaced_seen = True  # similar but not better — skip
                break
            if replaced_seen:
                continue

            prev = self._counts.get(sentence, 0)
            count = prev + 1 if sentence in self._counts else 1
            # Also bump if only whitespace-normalized form was counting under another string
            for old_s, old_c in self._counts.items():
                if old_s != sentence and normalize_for_compare(old_s) == key:
                    count = max(count, old_c + 1)
            next_counts[sentence] = count

            if count >= self.stable_threshold and key not in self._seen:
                self._seen.add(key)
                commits.append(("append", sentence))

        # Keep counts only for sentences still visible (and not yet seen).
        self._counts = {
            s: c
            for s, c in next_counts.items()
            if s in frame_set and normalize_for_compare(s) not in self._seen
        }
        return commits

    def flush_trailing(self, panel_text: str) -> list[tuple[CommitAction, str]]:
        """On stop: save last incomplete / not-yet-stable trailing text if useful."""
        commits: list[tuple[CommitAction, str]] = []
        for sentence in split_caption_sentences(panel_text):
            s = sentence.strip()
            if len(s) < self.min_length:
                continue
            key = normalize_for_compare(s)
            if key in self._seen:
                continue
            if any(similarity_ratio(s, seen) >= self.similarity for seen in self._seen):
                continue
            self._seen.add(key)
            commits.append(("append", s))
        self._counts.clear()
        return commits
