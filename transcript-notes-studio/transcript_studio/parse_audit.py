"""Audit raw vs cleaned transcripts — detect possible context / topic loss."""

from __future__ import annotations

import difflib
import re
from collections import Counter
from dataclasses import dataclass, field

from transcript_studio.cleanup import (
    aggressive_prefix_dedup,
    clean_transcript,
    dedupe_lines,
    maximal_prefix_dedup,
    normalize_segment,
    split_sentences,
)

_WORD_RE = re.compile(r"\b[a-z][a-z0-9'-]{2,}\b", re.I)
_STOPWORDS = frozenset(
    """
    the a an and or but in on at to for of is are was were be been being
    it this that with as by from not you we they he she i my our your their
    so if then than when what which who how all any each some no yes ok okay
    um uh er like just really very also about into over after before
    """.split()
)


@dataclass
class RemovedLine:
    text: str
    reason: str  # empty | exact_duplicate | prefix_merged | prefix_subsumed | aggressive_skip
    possibly_lost: bool = False


@dataclass
class ParseAuditReport:
    aggressive: bool
    raw_lines: int
    kept_lines: int
    raw_words: int
    clean_words: int
    raw_sentences: int
    clean_sentences: int
    word_retention_pct: float
    removed_lines: list[RemovedLine] = field(default_factory=list)
    suspicious_phrases: list[str] = field(default_factory=list)
    topic_words_dropped: list[tuple[str, int, int]] = field(default_factory=list)
    weak_sentence_matches: list[tuple[str, float]] = field(default_factory=list)
    cleaned_text: str = ""

    @property
    def lines_removed(self) -> int:
        return max(0, self.raw_lines - self.kept_lines)

    @property
    def likely_safe_removals(self) -> int:
        return sum(1 for r in self.removed_lines if not r.possibly_lost)

    @property
    def review_count(self) -> int:
        return sum(1 for r in self.removed_lines if r.possibly_lost) + len(
            self.suspicious_phrases
        )


def _word_count(text: str) -> int:
    return len(text.split())


def _content_words(text: str) -> Counter[str]:
    words = [m.group(0).lower() for m in _WORD_RE.finditer(text)]
    return Counter(w for w in words if w not in _STOPWORDS)


def _is_subsumed(line: str, kept_lines: list[str], cleaned_text: str) -> bool:
    line = line.strip()
    if not line:
        return True
    if line in cleaned_text:
        return True
    low = line.lower()
    if low in cleaned_text.lower():
        return True
    for kept in kept_lines:
        if kept.startswith(line) or line.startswith(kept):
            return True
    return False


def _dedupe_lines_audited(lines: list[str]) -> tuple[list[str], list[RemovedLine]]:
    removed: list[RemovedLine] = []
    if not lines:
        return [], removed
    out: list[str] = []
    for line in lines:
        line = line.strip()
        if not line:
            removed.append(RemovedLine("", "empty"))
            continue
        if out and out[-1] == line:
            removed.append(RemovedLine(line, "exact_duplicate"))
            continue
        if out and line.startswith(out[-1]) and len(line) > len(out[-1]):
            prev = out[-1]
            removed.append(RemovedLine(prev, "prefix_merged"))
            out[-1] = line
            continue
        out.append(line)
    return out, removed


def _maximal_prefix_dedup_audited(lines: list[str]) -> tuple[list[str], list[RemovedLine]]:
    removed: list[RemovedLine] = []
    out: list[str] = []
    for line in lines:
        line = line.strip()
        if not line:
            removed.append(RemovedLine("", "empty"))
            continue
        subsumed_from_out: list[str] = []
        new_out: list[str] = []
        for existing in out:
            if line.startswith(existing) and len(line) > len(existing):
                subsumed_from_out.append(existing)
            else:
                new_out.append(existing)
        if subsumed_from_out:
            for s in subsumed_from_out:
                removed.append(RemovedLine(s, "prefix_subsumed"))
            out = new_out
        if any(line.startswith(x) and len(x) >= len(line) for x in out):
            removed.append(RemovedLine(line, "prefix_subsumed"))
            continue
        out.append(line)
    return out, removed


def _aggressive_prefix_dedup_audited(lines: list[str]) -> tuple[list[str], list[RemovedLine]]:
    removed: list[RemovedLine] = []
    if len(lines) < 2:
        return lines, removed
    out: list[str] = []
    i = 0
    while i < len(lines):
        current = lines[i].strip()
        if not current:
            removed.append(RemovedLine("", "empty"))
            i += 1
            continue
        if i + 1 < len(lines):
            nxt = lines[i + 1].strip()
            if nxt.startswith(current) and len(nxt) > len(current):
                removed.append(RemovedLine(current, "aggressive_skip"))
                i += 1
                continue
        out.append(current)
        i += 1
    deduped, more_removed = _dedupe_lines_audited(out)
    removed.extend(more_removed)
    return deduped, removed


def _flag_removals(removed: list[RemovedLine], kept_lines: list[str], cleaned_text: str) -> None:
    _flag_removals_limited(removed, kept_lines, cleaned_text, max_check=len(removed))


def _topic_words_dropped(raw: str, cleaned: str, *, min_raw_count: int = 2) -> list[tuple[str, int, int]]:
    raw_c = _content_words(raw)
    clean_c = _content_words(cleaned)
    dropped: list[tuple[str, int, int]] = []
    for word, raw_n in raw_c.most_common(40):
        if raw_n < min_raw_count:
            break
        clean_n = clean_c.get(word, 0)
        if clean_n == 0:
            dropped.append((word, raw_n, 0))
        elif clean_n < raw_n * 0.35:
            dropped.append((word, raw_n, clean_n))
    return dropped[:15]


def _weak_sentence_matches(
    raw_text: str,
    cleaned: str,
    *,
    limit: int = 12,
    max_raw_sents: int = 150,
) -> list[tuple[str, float]]:
    """Raw sentences with low similarity to the nearest cleaned sentence."""
    raw_sents = split_sentences(raw_text)[:max_raw_sents]
    clean_sents = split_sentences(cleaned)
    if not raw_sents or not clean_sents:
        return []

    cleaned_joined = cleaned.lower()
    clean_sample = clean_sents if len(clean_sents) <= 80 else clean_sents[:: max(1, len(clean_sents) // 80)]
    weak: list[tuple[str, float]] = []
    seen: set[str] = set()

    for sent in raw_sents:
        if len(sent.split()) < 6:
            continue
        key = sent.lower()[:80]
        if key in seen:
            continue
        if sent.lower() in cleaned_joined:
            continue
        best = 0.0
        for other in clean_sample:
            ratio = difflib.SequenceMatcher(None, sent.lower(), other.lower()).ratio()
            if ratio > best:
                best = ratio
            if best >= 0.55:
                break
        if best < 0.55:
            weak.append((sent, round(best, 2)))
            seen.add(key)
        if len(weak) >= limit:
            break
    return weak


def _suspicious_phrases(removed: list[RemovedLine], *, limit: int = 10) -> list[str]:
    phrases: list[str] = []
    for item in removed:
        if not item.possibly_lost or not item.text:
            continue
        snippet = item.text if len(item.text) <= 160 else item.text[:157] + "…"
        phrases.append(f"[{item.reason}] {snippet}")
        if len(phrases) >= limit:
            break
    return phrases


def _flag_removals_limited(
    removed: list[RemovedLine], kept_lines: list[str], cleaned_text: str, *, max_check: int = 400
) -> None:
    flagged = 0
    for item in removed:
        if flagged >= max_check:
            break
        if not item.text or item.reason in {"empty", "exact_duplicate"}:
            item.possibly_lost = False
            continue
        item.possibly_lost = not _is_subsumed(item.text, kept_lines, cleaned_text)
        flagged += 1


def audit_parse(raw: str, *, aggressive: bool = False) -> ParseAuditReport:
    """Compare raw transcript to cleaned output and flag possible content loss."""
    raw_lines_in = [ln for ln in raw.splitlines() if ln.strip()]
    lines = [normalize_segment(ln) for ln in raw.splitlines()]
    lines = [ln for ln in lines if ln]

    if aggressive:
        kept_lines, removed = _maximal_prefix_dedup_audited(lines)
        # clean_transcript also runs filler pass on joined text — line audit is pre-join
    else:
        kept_lines, removed = _dedupe_lines_audited(lines)

    cleaned = clean_transcript(raw, aggressive=aggressive)
    _flag_removals_limited(removed, kept_lines, cleaned)

    raw_joined = " ".join(normalize_segment(ln) for ln in raw_lines_in)
    raw_words = _word_count(raw_joined)
    clean_words = _word_count(cleaned)
    retention = (clean_words / raw_words * 100.0) if raw_words else 100.0

    return ParseAuditReport(
        aggressive=aggressive,
        raw_lines=len(raw_lines_in),
        kept_lines=len(kept_lines),
        raw_words=raw_words,
        clean_words=clean_words,
        raw_sentences=len(split_sentences(raw_joined)),
        clean_sentences=len(split_sentences(cleaned)),
        word_retention_pct=round(retention, 1),
        removed_lines=removed,
        suspicious_phrases=_suspicious_phrases(removed),
        topic_words_dropped=_topic_words_dropped(raw_joined, cleaned),
        weak_sentence_matches=_weak_sentence_matches(raw_joined, cleaned),
        cleaned_text=cleaned,
    )


def format_audit_report(report: ParseAuditReport) -> str:
    """Human-readable audit for GUI / CLI."""
    mode = "aggressive" if report.aggressive else "standard"
    lines: list[str] = [
        f"=== Cleanup audit ({mode}) ===",
        "",
        "Counts",
        f"  Lines:     {report.raw_lines:,} -> {report.kept_lines:,} "
        f"({report.lines_removed:,} removed)",
        f"  Words:     {report.raw_words:,} -> {report.clean_words:,} "
        f"({report.word_retention_pct:.1f}% retained)",
        f"  Sentences: {report.raw_sentences:,} -> {report.clean_sentences:,}",
        "",
        "Dedup summary",
        f"  Likely safe removals (prefix growth / duplicates): {report.likely_safe_removals:,}",
        f"  Flagged for review: {report.review_count}",
        "",
    ]

    by_reason: Counter[str] = Counter(r.reason for r in report.removed_lines if r.text)
    if by_reason:
        lines.append("Removed by reason")
        for reason, count in by_reason.most_common():
            lines.append(f"  {reason}: {count}")
        lines.append("")

    if report.suspicious_phrases:
        lines.append("Possibly lost lines (not clearly subsumed in cleaned text)")
        for phrase in report.suspicious_phrases:
            lines.append(f"  - {phrase}")
        lines.append("")

    if report.weak_sentence_matches:
        lines.append("Weak sentence matches (raw sentence vs nearest cleaned)")
        for sent, score in report.weak_sentence_matches:
            snippet = sent if len(sent) <= 120 else sent[:117] + "…"
            lines.append(f"  - ({score:.0%}) {snippet}")
        lines.append("")

    if report.topic_words_dropped:
        lines.append("Topic words reduced or missing (content words, ≥2 mentions in raw)")
        for word, raw_n, clean_n in report.topic_words_dropped:
            if clean_n == 0:
                lines.append(f"  - {word}: {raw_n} -> gone")
            else:
                lines.append(f"  - {word}: {raw_n} -> {clean_n}")
        lines.append("")

    if report.review_count == 0 and not report.topic_words_dropped:
        lines.append("No obvious topic/sentence loss detected.")
        lines.append("Most removal is expected caption prefix dedup and filler stripping.")
    else:
        lines.append(
            "Tip: If flagged items look like real lecture content, try turning OFF "
            "aggressive dedup and re-parse."
        )

    return "\n".join(lines).strip() + "\n"


@dataclass
class NotesAuditReport:
    source_words: int
    notes_words: int
    source_chars: int
    notes_chars: int
    word_retention_pct: float
    topic_words_dropped: list[tuple[str, int, int]] = field(default_factory=list)
    weak_sentence_matches: list[tuple[str, float]] = field(default_factory=list)

    @property
    def review_count(self) -> int:
        return len(self.topic_words_dropped) + len(self.weak_sentence_matches)


_NOTE_ARTIFACT_MARKERS = ("## Backlinks", "## Slide captures", "---\n\n## Backlinks")


def _notes_plaintext(notes_md: str) -> str:
    """Strip galleries, backlinks, and code fences for retention comparison."""
    text = notes_md
    for marker in _NOTE_ARTIFACT_MARKERS:
        idx = text.find(marker)
        if idx >= 0:
            text = text[:idx]
    text = re.sub(r"```[\w]*\n.*?```", " ", text, flags=re.DOTALL)
    text = re.sub(r"\[\[[^\]]+\]\]", " ", text)
    text = re.sub(r"!\[[^\]]*\]\([^)]+\)", " ", text)
    text = re.sub(r"#{1,6}\s+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def audit_notes(cleaned_source: str, notes_md: str) -> NotesAuditReport:
    """Compare cleaned transcript to generated notes — flag possible summarization loss."""
    source = cleaned_source.strip()
    notes_plain = _notes_plaintext(notes_md)
    source_words = _word_count(source)
    notes_words = _word_count(notes_plain)
    retention = (notes_words / source_words * 100.0) if source_words else 100.0
    return NotesAuditReport(
        source_words=source_words,
        notes_words=notes_words,
        source_chars=len(source),
        notes_chars=len(notes_md),
        word_retention_pct=round(retention, 1),
        topic_words_dropped=_topic_words_dropped(source, notes_plain),
        weak_sentence_matches=_weak_sentence_matches(source, notes_plain, limit=15),
    )


def format_notes_audit_report(report: NotesAuditReport) -> str:
    lines: list[str] = [
        "=== Notes retention audit (cleaned transcript -> generated notes) ===",
        "",
        "Counts",
        f"  Source:  {report.source_chars:,} chars, {report.source_words:,} words (cleaned transcript)",
        f"  Notes:   {report.notes_chars:,} chars, {report.notes_words:,} words (body text, excl. code/slides)",
        f"  Retention: {report.word_retention_pct:.1f}% of source topic words in notes",
        "",
    ]
    if report.word_retention_pct < 8:
        lines.append("  Warning: Very low retention — notes are a heavy summary; much lecture detail may be missing.")
        lines.append("")
    elif report.word_retention_pct < 15:
        lines.append("  Note: Low retention is normal for summarization, but check topic words below.")
        lines.append("")

    if report.weak_sentence_matches:
        lines.append("Weak sentence matches (source sentence vs nearest notes text)")
        for sent, score in report.weak_sentence_matches:
            snippet = sent if len(sent) <= 120 else sent[:117] + "…"
            lines.append(f"  - ({score:.0%}) {snippet}")
        lines.append("")

    if report.topic_words_dropped:
        lines.append("Topic words reduced or missing in notes (≥2 mentions in source)")
        for word, raw_n, clean_n in report.topic_words_dropped:
            if clean_n == 0:
                lines.append(f"  - {word}: {raw_n} -> gone")
            else:
                lines.append(f"  - {word}: {raw_n} -> {clean_n}")
        lines.append("")

    if report.review_count == 0:
        lines.append("No obvious topic gaps vs cleaned transcript.")
        lines.append("Summaries always compress — compare Notes audit with Cleanup audit on Tune.")
    else:
        lines.append(
            "Tip: Raise max_llm_chunks in config, turn off Fast mode, or use Legacy pipeline "
            "for more coverage."
        )

    return "\n".join(lines).strip() + "\n"
