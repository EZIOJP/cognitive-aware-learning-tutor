"""Emit the JSON coding-question packs from the authoring modules.

    .venv\\Scripts\\python.exe scripts\\build_coding_questions.py
    .venv\\Scripts\\python.exe scripts\\validate_coding_questions.py

Writes one ``data/coding_questions/<pack_id>.json`` per authoring module plus an
``index.json`` manifest. Nothing here imports numpy/pandas, so it runs on any
interpreter; the validator is what needs the scientific stack.
"""

from __future__ import annotations

import importlib
import json
import pkgutil
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "data" / "coding_questions"
SRC_PACKAGE = "coding_questions_src"
sys.path.insert(0, str(Path(__file__).resolve().parent))


def discover_packs() -> list[dict[str, Any]]:
    import coding_questions_src as src

    packs: list[dict[str, Any]] = []
    for info in sorted(pkgutil.iter_modules(src.__path__), key=lambda m: m.name):
        module = importlib.import_module(f"{SRC_PACKAGE}.{info.name}")
        built = getattr(module, "PACK", None)
        if built:
            packs.append(built)
    return packs


def build_index(packs: list[dict[str, Any]]) -> dict[str, Any]:
    entries = []
    for p in packs:
        questions = p["questions"]
        entries.append(
            {
                "pack_id": p["pack_id"],
                "file": f"{p['pack_id']}.json",
                "title": p["title"],
                "topic": p["topic"],
                "summary": p.get("summary", ""),
                "question_count": len(questions),
                "test_case_count": sum(len(q["test_cases"]) for q in questions),
                "edge_case_count": sum(
                    1 for q in questions for c in q["test_cases"] if c["is_edge_case"]
                ),
                "difficulties": {
                    level: sum(1 for q in questions if q["difficulty"] == level)
                    for level in ("easy", "medium", "hard")
                },
                "topic_ids": sorted({q["topic_id"] for q in questions if q.get("topic_id")}),
                "requires": p.get("requires", []),
            }
        )
    return {
        "schema_version": "1.0",
        "domain": "coding",
        "language": "python",
        "format_doc": "docs/CODING_QUESTION_FORMAT.md",
        "pack_count": len(entries),
        "question_count": sum(e["question_count"] for e in entries),
        "test_case_count": sum(e["test_case_count"] for e in entries),
        "edge_case_count": sum(e["edge_case_count"] for e in entries),
        "packs": entries,
    }


def main() -> int:
    packs = discover_packs()
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    for p in packs:
        path = OUT_DIR / f"{p['pack_id']}.json"
        path.write_text(json.dumps(p, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"wrote {path.relative_to(ROOT)}  ({len(p['questions'])} questions)")

    index = build_index(packs)
    (OUT_DIR / "index.json").write_text(
        json.dumps(index, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(
        f"wrote index.json — {index['pack_count']} packs, "
        f"{index['question_count']} questions, {index['test_case_count']} test cases "
        f"({index['edge_case_count']} edge cases)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
