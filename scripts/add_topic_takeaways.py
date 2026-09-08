#!/usr/bin/env python3
"""Insert post-code Takeaway paragraphs for selected thin topics."""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.topic_deep_enrichments import TAKEAWAYS

NOTES_DIR = ROOT / "data" / "notes"
TOPIC_HEADING_RE = re.compile(
    r"^## `?(L\d+-T\d+)`?\s*(?:—|-|–|:)\s*.+",
    re.MULTILINE | re.IGNORECASE,
)
FENCE_RE = re.compile(r"```[\w]*[^\n]*\n[\s\S]*?```", re.MULTILINE)
TAKEAWAY_RE = re.compile(r"\*\*Takeaway:\*\*", re.IGNORECASE)


def _insert_after_last_fence(body: str, takeaway: str) -> str:
    if TAKEAWAY_RE.search(body):
        return body
    matches = list(FENCE_RE.finditer(body))
    if not matches:
        return body
    pos = matches[-1].end()
    block = f"\n\n**Takeaway:** {takeaway.strip()}\n"
    return body[:pos] + block + body[pos:]


def _normalize_separators(text: str) -> str:
    text = re.sub(r"(---\n){2,}", "---\n\n", text)
    text = re.sub(r"\n{4,}", "\n\n\n", text)
    return text


def add_takeaways(path: Path) -> tuple[int, bool]:
    raw = path.read_text(encoding="utf-8")
    matches = list(TOPIC_HEADING_RE.finditer(raw))
    if not matches:
        return 0, False

    out = raw
    added = 0
    for i in range(len(matches) - 1, -1, -1):
        m = matches[i]
        tid_m = re.search(r"(L\d+-T\d+)", m.group(0), re.I)
        if not tid_m:
            continue
        tid = tid_m.group(1).upper()
        takeaway = TAKEAWAYS.get(tid)
        if not takeaway:
            continue

        body_start = m.end()
        body_end = matches[i + 1].start() if i + 1 < len(matches) else len(out)
        body = out[body_start:body_end]
        new_body = _insert_after_last_fence(body, takeaway)
        if new_body != body:
            out = out[:body_start] + new_body + out[body_end:]
            added += 1

    cleaned = _normalize_separators(out)
    changed = cleaned != raw
    if changed:
        path.write_text(cleaned, encoding="utf-8")
    return added, changed


def main() -> None:
    total = 0
    for path in sorted(NOTES_DIR.glob("L*.md")):
        n, changed = add_takeaways(path)
        flag = "updated" if changed else "unchanged"
        print(f"{path.name}: +{n} takeaways ({flag})")
        total += n
    print(f"done ({total} takeaways added)")


if __name__ == "__main__":
    main()
