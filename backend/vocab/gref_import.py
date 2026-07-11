"""Parse and dedupe GRE word lists from gref_material/gre words/."""

from __future__ import annotations

import csv
import io
import re
from pathlib import Path
from typing import Any

from backend.paths import GREF_MATERIAL_DIR

_JUNK_RE = re.compile(r"[?？]{2,}|;?\s*[?？]+")
_MAX_EXAMPLES = 5
_THIN_MEANING_CHARS = 12


def display_lemma(raw: str) -> str:
    """Canonical display form: Title Case tokens (Abate, Not Abate)."""
    text = re.sub(r"\s+", " ", (raw or "").strip())
    if not text:
        return ""
    parts = []
    for token in text.split(" "):
        if not token:
            continue
        if "-" in token:
            parts.append("-".join(p[:1].upper() + p[1:].lower() if p else "" for p in token.split("-")))
        else:
            parts.append(token[:1].upper() + token[1:].lower())
    return " ".join(parts)


def lemma_key(raw: str) -> str:
    return display_lemma(raw).lower()


def clean_meaning(raw: str) -> str:
    text = (raw or "").strip()
    text = _JUNK_RE.sub("", text)
    text = re.sub(r"\s+", " ", text).strip(" ;,")
    return text


def has_usable_meaning(word: dict[str, Any]) -> bool:
    return len(str(word.get("meaning") or "").strip()) >= 3


def is_thin_card(word: dict[str, Any]) -> bool:
    meaning = str(word.get("meaning") or "").strip()
    if len(meaning) < _THIN_MEANING_CHARS:
        return True
    examples = word.get("examples") or []
    if not examples:
        return True
    return False


def _source_tag(path: Path) -> str:
    return path.stem.lower().replace(" ", "_")


def _parse_txt(path: Path) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    text = path.read_text(encoding="utf-8", errors="replace")
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if ":" not in line:
            continue
        left, right = line.split(":", 1)
        word = display_lemma(left)
        meaning = clean_meaning(right)
        if not word:
            continue
        out.append(
            {
                "word": word,
                "meaning": meaning,
                "examples": [],
                "tags": [],
                "sources": [_source_tag(path)],
            }
        )
    return out


def _example_list_from_row(row: dict[str, str]) -> list[dict[str, str]]:
    examples: list[dict[str, str]] = []
    single = (row.get("example") or "").strip()
    if single:
        examples.append({"text": single})
    for i in range(1, 6):
        s = (row.get(f"s{i}") or "").strip()
        if s:
            examples.append({"text": s})
    return examples[:_MAX_EXAMPLES]


def _parse_csv(path: Path) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    raw = path.read_text(encoding="utf-8", errors="replace")
    reader = csv.DictReader(io.StringIO(raw))
    if not reader.fieldnames:
        return out
    fields = {f.lower().strip(): f for f in reader.fieldnames if f}
    word_col = fields.get("word")
    meaning_col = fields.get("meaning") or fields.get("definition")
    if not word_col:
        return out
    pos_col = fields.get("part of speech") or fields.get("pos")
    for row in reader:
        word = display_lemma(str(row.get(word_col) or ""))
        if not word:
            continue
        meaning = clean_meaning(str(row.get(meaning_col) or "")) if meaning_col else ""
        # Strip leading POS markers like "(v) " already in definition
        examples = _example_list_from_row({k.lower(): str(v or "") for k, v in row.items() if k})
        tags: list[str] = []
        if pos_col:
            pos = str(row.get(pos_col) or "").strip()
            if pos:
                tags.append(pos.lower())
        item: dict[str, Any] = {
            "word": word,
            "meaning": meaning,
            "examples": examples,
            "tags": tags,
            "sources": [_source_tag(path)],
        }
        out.append(item)
    return out


def parse_gref_file(path: Path) -> list[dict[str, Any]]:
    suffix = path.suffix.lower()
    if suffix == ".txt":
        return _parse_txt(path)
    if suffix == ".csv":
        return _parse_csv(path)
    return []


def _merge_entry(existing: dict[str, Any], incoming: dict[str, Any]) -> dict[str, Any]:
    out = dict(existing)
    em = str(existing.get("meaning") or "").strip()
    im = str(incoming.get("meaning") or "").strip()
    if len(im) > len(em):
        out["meaning"] = im
    elif not em and im:
        out["meaning"] = im

    seen_ex = {
        str(e.get("text") if isinstance(e, dict) else e).strip().lower()
        for e in (existing.get("examples") or [])
        if e
    }
    examples = list(existing.get("examples") or [])
    for ex in incoming.get("examples") or []:
        text = str(ex.get("text") if isinstance(ex, dict) else ex).strip()
        if not text:
            continue
        key = text.lower()
        if key in seen_ex:
            continue
        seen_ex.add(key)
        examples.append({"text": text} if isinstance(ex, dict) else {"text": text})
        if len(examples) >= _MAX_EXAMPLES:
            break
    out["examples"] = examples[:_MAX_EXAMPLES]

    tags = list(existing.get("tags") or [])
    for t in incoming.get("tags") or []:
        tl = str(t).strip().lower()
        if tl and tl not in {str(x).lower() for x in tags}:
            tags.append(tl)
    out["tags"] = tags

    sources = list(existing.get("sources") or [])
    for s in incoming.get("sources") or []:
        if s and s not in sources:
            sources.append(s)
    out["sources"] = sources
    out["word"] = display_lemma(str(out.get("word") or incoming.get("word") or ""))
    return out


def priority_from_sources(sources: list[str] | None) -> int:
    """Higher = appears in more lists (study these first). Scale 1–5."""
    n = len(sources or [])
    if n >= 8:
        return 5
    if n >= 5:
        return 4
    if n >= 3:
        return 3
    if n >= 2:
        return 2
    return 1


def priority_label(priority: int) -> str:
    if priority >= 5:
        return "core"
    if priority >= 4:
        return "high"
    if priority >= 3:
        return "medium"
    if priority >= 2:
        return "low"
    return "rare"


def apply_priority_fields(entry: dict[str, Any]) -> dict[str, Any]:
    out = dict(entry)
    sources = list(out.get("sources") or [])
    p = int(out.get("priority") or 0) or priority_from_sources(sources)
    out["priority"] = p
    out["priority_label"] = priority_label(p)
    out["source_count"] = len(sources)
    return out


def sort_by_priority(words: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Highest priority first, then alphabetical — groups 1+ become the high-overlap set."""
    decorated = [apply_priority_fields(w) for w in words]
    decorated.sort(
        key=lambda w: (-int(w.get("priority") or 0), -int(w.get("source_count") or 0), str(w.get("word") or "").lower())
    )
    for i, w in enumerate(decorated):
        w["id"] = i + 1
    return decorated


def dedupe_entries(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_key: dict[str, dict[str, Any]] = {}
    order: list[str] = []
    for entry in entries:
        key = lemma_key(str(entry.get("word") or ""))
        if not key:
            continue
        if key not in by_key:
            by_key[key] = {
                "word": display_lemma(str(entry.get("word") or "")),
                "meaning": clean_meaning(str(entry.get("meaning") or "")),
                "examples": list(entry.get("examples") or [])[:_MAX_EXAMPLES],
                "tags": list(entry.get("tags") or []),
                "sources": list(entry.get("sources") or []),
                "pronunciation": "",
                "story_mnemonic": "",
                "etymology": "",
                "synonyms": [],
                "antonyms": [],
            }
            order.append(key)
        else:
            by_key[key] = _merge_entry(by_key[key], entry)
    return sort_by_priority([apply_priority_fields(by_key[k]) for k in order])


def collect_gref_entries(folder: Path | None = None) -> list[dict[str, Any]]:
    root = folder or GREF_MATERIAL_DIR
    if not root.is_dir():
        raise FileNotFoundError(f"GRE material folder not found: {root}")
    raw: list[dict[str, Any]] = []
    files = sorted(
        [p for p in root.iterdir() if p.is_file() and p.suffix.lower() in {".txt", ".csv"}],
        key=lambda p: p.name.lower(),
    )
    for path in files:
        raw.extend(parse_gref_file(path))
    return dedupe_entries(raw)


def merge_into_bank(
    existing: list[dict[str, Any]],
    imported: list[dict[str, Any]],
    *,
    replace: bool = False,
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    """
    Merge imported lemmas into the bank.
    Returns (words, stats) with stats keys: added, updated, skipped, total.
    """
    if replace:
        out = sort_by_priority([apply_priority_fields(dict(item)) for item in imported])
        return out, {
            "added": len(out),
            "updated": 0,
            "skipped": 0,
            "total": len(out),
        }

    by_key = {lemma_key(str(w.get("word") or "")): dict(w) for w in existing}
    order = [lemma_key(str(w.get("word") or "")) for w in existing]
    next_id = max((int(w.get("id") or 0) for w in existing), default=0) + 1
    added = updated = skipped = 0

    for item in imported:
        key = lemma_key(str(item.get("word") or ""))
        if not key:
            skipped += 1
            continue
        if key in by_key:
            before = by_key[key]
            merged = apply_priority_fields(_merge_entry(before, item))
            if (
                str(merged.get("meaning") or "") != str(before.get("meaning") or "")
                or len(merged.get("examples") or []) != len(before.get("examples") or [])
                or int(merged.get("priority") or 0) != int(before.get("priority") or 0)
            ):
                updated += 1
            else:
                skipped += 1
            by_key[key] = merged
        else:
            row = apply_priority_fields(dict(item))
            row["id"] = next_id
            next_id += 1
            by_key[key] = row
            order.append(key)
            added += 1

    out = sort_by_priority([by_key[k] for k in order if k in by_key])
    return out, {
        "added": added,
        "updated": updated,
        "skipped": skipped,
        "total": len(out),
    }


def dry_run_stats(folder: Path | None = None) -> dict[str, Any]:
    entries = collect_gref_entries(folder)
    with_meaning = sum(1 for e in entries if has_usable_meaning(e))
    return {
        "unique_words": len(entries),
        "with_meaning": with_meaning,
        "stubs": len(entries) - with_meaning,
        "folder": str(folder or GREF_MATERIAL_DIR),
    }
