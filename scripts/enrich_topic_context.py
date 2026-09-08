#!/usr/bin/env python3
"""Add short context blurbs to topic sections that jump straight into code."""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.transcripts.note_topics import parse_note_topics

NOTES_DIR = ROOT / "data" / "notes"
INDEX_ROW_RE = re.compile(
    r"\|\s*`?(L\d+-T\d+)`?\s*\|\s*([^|]+)\|\s*([^|]+)\|",
    re.IGNORECASE,
)
TOPIC_HEADING_RE = re.compile(
    r"^(## `?(L\d+-T\d+)`?\s*(?:—|-|–|:)\s*.+)$",
    re.MULTILINE | re.IGNORECASE,
)
CONTEXT_LINE_RE = re.compile(r"^>\s*\*?\*?(context|focus|why this|in context|self-check)", re.I)
CODE_LIKE = re.compile(
    r"^[\w.]+\s*=|^print\(|^subgraph|^array\(|^np\.|^pd\.|^df\.|^import\s|^def\s",
    re.I,
)


def _prose_scope(scope: str) -> str | None:
    s = (scope or "").strip()
    if len(s) < 28 or CODE_LIKE.match(s):
        return None
    if s.startswith("- "):
        s = s[2:]
    if s.startswith("**") and "**" in s[2:]:
        s = s.strip("*").strip()
    return s[:220].strip() or None


def _fallback_context(title: str) -> str:
    t = title.lower()
    if "visual" in t:
        return "Visual map — read the diagram first, then connect it to the code examples."
    if "quiz" in t:
        return "Self-check: predict the output before running the cell."
    if "setup" in t:
        return "Shared setup — bookmark these arrays; later examples reuse the same variables."
    if "recap" in t:
        return "Bridge from the prior lecture — skim if the pipeline is already familiar."
    if "doubt" in t or "q&a" in t:
        return "Class Q&A — common sticking points called out explicitly."
    if "pre-read" in t or "carried" in t:
        return "Pre-read / bridge material — lighter coverage here, expanded in the next lecture."
    if "broadcast" in t:
        return "Shape rules matter — sketch dimensions before trusting the output."
    if "matrix mult" in t or "matmul" in t or " dot" in f" {t}":
        return "Not element-wise multiply — confirm shapes before calling `np.dot` / `@`."
    if "iloc" in t or ".loc" in t:
        return "Selection rules: `iloc` stops before the end index; `loc` includes the end label."
    if "merge" in t or "concat" in t:
        return "Pick the right join tool — stacking vs key-based merge solve different problems."
    if "boolean" in t or "mask" in t:
        return "Use `&` / `|` with parentheses — Python `and` / `or` will not work on Series."
    if "reshape" in t or "transpose" in t:
        return "Layout change only — total element count must stay the same for reshape."
    if "fancy" in t:
        return "Filter or reorder without a loop — the mask must match the array length."
    if "vectoriz" in t:
        return "Whole-array execution in compiled code — avoid Python loops when shapes align."
    if "pandas" in t and "intro" in t:
        return "NumPy handles numbers; pandas adds labeled tables — both show up in real pipelines."
    if "aggregate" in t or "axis" in t:
        return "Axis choice changes the answer — draw the collapse direction before calling `.sum()`."
    if "sort" in t:
        return "Sorting returns a new array unless you use the in-place `.sort()` method."
    if "unique" in t or "duplicate" in t:
        return "Data quality step — know whether you need distinct values, counts, or row removal."
    if "apply" in t or "lambda" in t:
        return "Row/cell-wise Python logic — prefer vectorized ops when a built-in exists."
    return f"Focus: {title.strip()}."


def _needs_context(body: str) -> bool:
    lines = [ln for ln in (body or "").splitlines() if ln.strip()]
    if not lines:
        return True
    for ln in lines[:4]:
        if CONTEXT_LINE_RE.match(ln.strip()):
            return False
    first = lines[0].strip()
    if first.startswith("```") or first.startswith("|") or first.startswith("!["):
        return True
    if first == "---" and len(lines) > 1 and lines[1].strip().startswith("```"):
        return True
    if len(first) < 20 and len(lines) > 1 and lines[1].strip().startswith("```"):
        return True
    return False


def _parse_index_scopes(text: str) -> dict[str, dict[str, str]]:
    found: dict[str, dict[str, str]] = {}
    anchor = "## 🗂️ Topic Index"
    if anchor not in text:
        return found
    chunk = text[text.index(anchor) :]
    end_m = re.search(r"\n## [^#|\n]", chunk[len(anchor) :])
    if end_m:
        chunk = chunk[: len(anchor) + end_m.start()]
    for m in INDEX_ROW_RE.finditer(chunk):
        tid = m.group(1).upper()
        found[tid] = {"title": m.group(2).strip(), "scope": m.group(3).strip()}
    return found


def enrich_note(path: Path) -> int:
    raw = path.read_text(encoding="utf-8")
    index = _parse_index_scopes(raw)
    topics = {t.topic_id.upper(): t for t in parse_note_topics(raw, min_body_chars=20)}

    matches = list(TOPIC_HEADING_RE.finditer(raw))
    if not matches:
        return 0

    inserts: list[tuple[int, str]] = []
    for i, m in enumerate(matches):
        heading = m.group(1)
        tid_m = re.search(r"L\d+-T\d+", heading, re.I)
        if not tid_m:
            continue
        tid = tid_m.group(0).upper()
        body_start = m.end()
        body_end = matches[i + 1].start() if i + 1 < len(matches) else len(raw)
        body = raw[body_start:body_end]
        if not _needs_context(body):
            continue

        topic = topics.get(tid)
        title = topic.title if topic else heading
        scope_row = index.get(tid, {})
        scope = _prose_scope(scope_row.get("scope", ""))
        blurb = scope or _fallback_context(title)
        line = f"\n\n> **Context:** {blurb}\n"
        inserts.append((body_start, line))

    if not inserts:
        return 0

    out = raw
    for pos, line in reversed(inserts):
        out = out[:pos] + line + out[pos:]

    path.write_text(out, encoding="utf-8")
    return len(inserts)


def main() -> None:
    total = 0
    for path in sorted(NOTES_DIR.glob("L*.md")):
        n = enrich_note(path)
        print(f"{path.name}: +{n} context lines")
        total += n
    print(f"done ({total} total)")


if __name__ == "__main__":
    main()
