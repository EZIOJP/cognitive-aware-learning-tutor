"""Contract tests: Python mermaid pipeline matches shared fixtures."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from backend.transcripts.mermaid.pipeline import layout_safe_mermaid_source, sanitize_mermaid_source

FIXTURES = json.loads((Path(__file__).parent / "fixtures" / "mermaid_cases.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize("case", FIXTURES, ids=[c["id"] for c in FIXTURES])
def test_mermaid_fixture_contract(case: dict) -> None:
    fn = layout_safe_mermaid_source if case.get("layout_safe") else sanitize_mermaid_source
    out = fn(case["input"])
    for fragment in case.get("expect_contains", []):
        assert fragment in out, f"missing {fragment!r} in:\n{out}"
    for fragment in case.get("expect_not_contains", []):
        assert fragment not in out, f"unexpected {fragment!r} in:\n{out}"
    if case.get("max_header_count") is not None:
        count = out.lower().count("flowchart td")
        assert count <= case["max_header_count"]
