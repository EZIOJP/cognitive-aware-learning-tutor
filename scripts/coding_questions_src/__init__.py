"""Authoring source for the coding-questions dataset.

The JSON packs under ``data/coding_questions/`` are the artifact the app loads;
these modules are where the content is written and edited. Multi-line Python
solutions are unreadable once escaped into JSON, so author here and run
``scripts/build_coding_questions.py`` to emit the packs, then
``scripts/validate_coding_questions.py`` to prove every solution passes every
test case.
"""

from __future__ import annotations

import textwrap
from typing import Any, Iterable, Sequence

SCHEMA_VERSION = "1.0"

NOTE_PATH_BY_LECTURE = {
    "L2": "L02_numpy_operations_notes.md",
    "L3": "L03_numpy_lecture3_notes.md",
    "L4": "L04_vectorization_stacking_pandas_notes.md",
    "L5": "L05_pandas_operations_notes.md",
}


def dedent(code: str) -> str:
    """Normalise a triple-quoted code block into a clean module-level snippet."""
    return textwrap.dedent(code).strip("\n") + "\n"


def case(
    name: str,
    *,
    expected: str,
    teaches: str,
    args: Sequence[str] = (),
    kwargs: dict[str, str] | None = None,
    edge: bool = False,
    compare: str | None = None,
    raises: bool = False,
) -> dict[str, Any]:
    """One test case. ``args``/``kwargs``/``expected`` are Python expressions.

    Expressions are strings so a pack stays valid JSON and the app can show the
    exact call it is about to run. They are evaluated with ``np``/``pd``/``math``
    in scope but **without** the reference solution, so an expectation can never
    be written in terms of the answer.
    """
    payload: dict[str, Any] = {
        "name": name,
        "input": {"args": list(args), "kwargs": dict(kwargs or {})},
        "expected": expected,
        "is_edge_case": bool(edge),
        "teaches": teaches,
    }
    if raises:
        payload["expected_kind"] = "raises"
    if compare:
        payload["compare"] = compare
    return payload


def question(
    *,
    id: str,
    title: str,
    topic: str,
    difficulty: str,
    concept: str,
    prompt: str,
    starter_code: str,
    solution: str,
    entry_point: str,
    tests: Iterable[dict[str, Any]],
    explanation: str,
    hints: Sequence[str],
    topic_id: str | None = None,
    tags: Sequence[str] = (),
    pitfalls: Sequence[str] = (),
    requires: Sequence[str] = (),
) -> dict[str, Any]:
    hint_list = [h.strip() for h in hints]
    payload: dict[str, Any] = {
        "id": id,
        "title": title,
        "topic": topic,
        "difficulty": difficulty,
        "language": "python",
        "concept": concept.strip(),
        "prompt": textwrap.dedent(prompt).strip(),
        "starter_code": dedent(starter_code),
        "solution": dedent(solution),
        "entry_point": entry_point,
        "test_cases": list(tests),
        "explanation": textwrap.dedent(explanation).strip(),
        # `hint` (singular) keeps the record assignable to the existing CodeDrill
        # shape in src/components/study/studySessionTypes.ts.
        "hint": hint_list[0],
        "hints": hint_list,
    }
    if topic_id:
        payload["topic_id"] = topic_id
        lecture = topic_id.split("-")[0].upper()
        note = NOTE_PATH_BY_LECTURE.get(lecture)
        if note:
            payload["note_path"] = note
    if tags:
        payload["tags"] = list(tags)
    if pitfalls:
        payload["pitfalls"] = list(pitfalls)
    if requires:
        payload["requires"] = list(requires)
    return payload


def pack(
    *,
    pack_id: str,
    title: str,
    topic: str,
    summary: str,
    questions: Sequence[dict[str, Any]],
    source_notes: Sequence[str] = (),
    requires: Sequence[str] = (),
) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "pack_id": pack_id,
        "title": title,
        "domain": "coding",
        "language": "python",
        "topic": topic,
        "summary": textwrap.dedent(summary).strip(),
        "source_notes": list(source_notes),
        "requires": list(requires),
        "questions": list(questions),
    }
