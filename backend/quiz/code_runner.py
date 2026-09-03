"""Run authored coding questions against their test cases.

Local-first: the user's own submission runs in a short-lived child interpreter with a
timeout, and each test case is compared by JSON-normalized equality (numpy/pandas aware).
This is the single grader for ``kind: coding`` items — the quiz handler calls
:func:`grade_submission` from the existing submit path, and the UI "Run tests" panel calls
the same function through ``POST /api/quiz/code/run``.

Contract for the JSON shape: docs/QUESTION_CONTENT_FORMAT.md
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

DEFAULT_TIMEOUT_SEC = 15
MAX_CODE_CHARS = 40_000
FLOAT_REL_TOL = 1e-6

# Executed inside the child interpreter. Reads a JSON job on argv[1], writes JSON results
# to stdout after a sentinel so user prints cannot corrupt the payload.
_SENTINEL = "__CALT_RESULTS__"

_HARNESS = '''
import json, sys, io, traceback, contextlib

SENTINEL = "__CALT_RESULTS__"

def normalize(value):
    """JSON-friendly view of a return value (numpy / pandas / set / tuple aware)."""
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    tolist = getattr(value, "tolist", None)
    if callable(tolist):
        try:
            return normalize(tolist())
        except Exception:
            pass
    to_dict = getattr(value, "to_dict", None)
    if callable(to_dict):
        try:
            return normalize(to_dict())
        except Exception:
            pass
    if isinstance(value, dict):
        return {str(k): normalize(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [normalize(v) for v in value]
    if isinstance(value, (set, frozenset)):
        try:
            return sorted(normalize(v) for v in value)
        except TypeError:
            return sorted(str(v) for v in value)
    item = getattr(value, "item", None)
    if callable(item):
        try:
            return normalize(item())
        except Exception:
            pass
    return repr(value)


def main():
    job = json.loads(sys.argv[1])
    results = []
    namespace = {"__name__": "__calt_submission__"}
    setup = job.get("setup_code") or ""
    code = job.get("code") or ""
    entry_point = job.get("entry_point") or ""

    try:
        if setup.strip():
            exec(compile(setup, "<setup>", "exec"), namespace)
        exec(compile(code, "<submission>", "exec"), namespace)
    except Exception:
        print(SENTINEL + json.dumps({
            "compile_error": traceback.format_exc(limit=4).strip(),
            "results": [],
        }))
        return

    fn = namespace.get(entry_point) if entry_point else None
    if entry_point and not callable(fn):
        print(SENTINEL + json.dumps({
            "compile_error": "Your code must define a function named '%s'." % entry_point,
            "results": [],
        }))
        return

    for case in job.get("test_cases") or []:
        row = {"name": case.get("name") or "test", "actual": None, "error": None, "stdout": ""}
        buf = io.StringIO()
        try:
            if entry_point:
                with contextlib.redirect_stdout(buf):
                    row["actual"] = normalize(
                        fn(*(case.get("input") or []), **(case.get("kwargs") or {}))
                    )
            else:
                sys.stdin = io.StringIO(case.get("stdin") or "")
                local_ns = dict(namespace)
                with contextlib.redirect_stdout(buf):
                    exec(compile(code, "<submission>", "exec"), local_ns)
                row["actual"] = None
        except Exception as exc:
            row["error"] = "%s: %s" % (type(exc).__name__, exc)
        row["stdout"] = buf.getvalue()[:4000]
        results.append(row)

    print(SENTINEL + json.dumps({"compile_error": None, "results": results}))


main()
'''


@dataclass
class TestOutcome:
    name: str
    passed: bool
    is_edge_case: bool = False
    description: str = ""
    hidden: bool = False
    expected: Any = None
    actual: Any = None
    error: str | None = None
    stdout: str = ""


@dataclass
class RunResult:
    passed: int = 0
    total: int = 0
    all_passed: bool = False
    compile_error: str | None = None
    timed_out: bool = False
    outcomes: list[TestOutcome] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        outcomes = [asdict(o) for o in self.outcomes]
        return {
            "passed": self.passed,
            "total": self.total,
            "all_passed": self.all_passed,
            "compile_error": self.compile_error,
            "timed_out": self.timed_out,
            "outcomes": outcomes,
            "results": outcomes,
        }


def _values_match(expected: Any, actual: Any) -> bool:
    if isinstance(expected, bool) or isinstance(actual, bool):
        return expected == actual
    if isinstance(expected, (int, float)) and isinstance(actual, (int, float)):
        if expected == actual:
            return True
        scale = max(abs(float(expected)), abs(float(actual)), 1.0)
        return abs(float(expected) - float(actual)) <= FLOAT_REL_TOL * scale
    if isinstance(expected, list) and isinstance(actual, list):
        return len(expected) == len(actual) and all(
            _values_match(e, a) for e, a in zip(expected, actual, strict=False)
        )
    if isinstance(expected, dict) and isinstance(actual, dict):
        if set(map(str, expected)) != set(map(str, actual)):
            return False
        norm_actual = {str(k): v for k, v in actual.items()}
        return all(_values_match(v, norm_actual[str(k)]) for k, v in expected.items())
    return expected == actual


def _stdout_match(expected: str, actual: str) -> bool:
    exp_lines = [line.rstrip() for line in str(expected).strip().splitlines()]
    act_lines = [line.rstrip() for line in str(actual).strip().splitlines()]
    return exp_lines == act_lines


def run_test_cases(
    *,
    code: str,
    test_cases: list[dict[str, Any]],
    entry_point: str = "",
    setup_code: str = "",
    language: str = "python",
    timeout_sec: int = DEFAULT_TIMEOUT_SEC,
) -> RunResult:
    """Execute ``code`` against ``test_cases`` and report per-case outcomes."""
    cases = [c for c in (test_cases or []) if isinstance(c, dict)]
    if (language or "python").lower() != "python":
        return RunResult(
            compile_error=f"{language} submissions are not executable yet — graded on review.",
            total=len(cases),
        )
    if not cases:
        return RunResult(compile_error="This question has no test cases.", total=0)
    if not (code or "").strip():
        return RunResult(compile_error="Write some code first.", total=len(cases))
    if len(code) > MAX_CODE_CHARS:
        return RunResult(compile_error="Submission is too large to run.", total=len(cases))

    job = {
        "code": code,
        "setup_code": setup_code or "",
        "entry_point": entry_point or "",
        "test_cases": [
            {
                "name": c.get("name") or f"test_{i + 1}",
                "input": c.get("input") or [],
                "kwargs": c.get("kwargs") or {},
                "stdin": c.get("stdin") or "",
            }
            for i, c in enumerate(cases)
        ],
    }

    with tempfile.TemporaryDirectory(prefix="calt-code-") as tmp:
        harness_path = Path(tmp) / "_calt_harness.py"
        harness_path.write_text(_HARNESS, encoding="utf-8")
        try:
            proc = subprocess.run(  # noqa: S603 - local-first, user's own submission
                [sys.executable, "-I", str(harness_path), json.dumps(job)],
                capture_output=True,
                text=True,
                timeout=timeout_sec,
                cwd=tmp,
            )
        except subprocess.TimeoutExpired:
            return RunResult(
                total=len(cases),
                timed_out=True,
                compile_error=f"Timed out after {timeout_sec}s — check for an infinite loop.",
            )

    payload: dict[str, Any] = {}
    stdout = proc.stdout or ""
    if _SENTINEL in stdout:
        try:
            payload = json.loads(stdout.rsplit(_SENTINEL, 1)[1].strip())
        except json.JSONDecodeError:
            payload = {}
    if not payload:
        detail = (proc.stderr or stdout or "").strip()[-800:]
        return RunResult(
            total=len(cases),
            compile_error=detail or "The submission produced no result.",
        )
    if payload.get("compile_error"):
        return RunResult(total=len(cases), compile_error=str(payload["compile_error"]))

    rows = payload.get("results") or []
    outcomes: list[TestOutcome] = []
    for i, case in enumerate(cases):
        row = rows[i] if i < len(rows) else {}
        error = row.get("error")
        script_mode = case.get("expected_stdout") is not None
        expected = case.get("expected_stdout") if script_mode else case.get("expected_output")
        actual = row.get("stdout", "") if script_mode else row.get("actual")
        if error:
            passed = False
        elif script_mode:
            passed = _stdout_match(str(expected or ""), str(actual or ""))
        else:
            passed = _values_match(expected, actual)
        outcomes.append(
            TestOutcome(
                name=str(case.get("name") or f"test_{i + 1}"),
                passed=passed,
                is_edge_case=bool(case.get("is_edge_case")),
                description=str(case.get("description") or ""),
                hidden=bool(case.get("hidden")),
                expected=expected,
                actual=actual,
                error=error,
                stdout=str(row.get("stdout") or "")[:2000],
            )
        )

    passed = sum(1 for o in outcomes if o.passed)
    return RunResult(
        passed=passed,
        total=len(outcomes),
        all_passed=passed == len(outcomes) and len(outcomes) > 0,
        outcomes=outcomes,
    )


def grade_submission(item: dict[str, Any], response: str) -> tuple[bool, str, dict[str, Any]]:
    """Grade one coding item. Returns ``(correct, feedback, run_payload)``.

    Items without test cases keep the legacy "did you make a real attempt" behaviour so
    LLM-generated code drills from lecture notes still work.
    """
    cases = [c for c in (item.get("test_cases") or []) if isinstance(c, dict)]
    if not cases:
        starter = str(item.get("starter_code") or "").strip()
        submitted = (response or "").strip()
        substantive = len(submitted) >= 12 and not submitted.lstrip().startswith("# TODO")
        correct = submitted != starter and substantive
        feedback = (
            "Submitted for review."
            if correct
            else "Edit the starter code with a real attempt before submitting."
        )
        return correct, feedback, {}

    result = run_test_cases(
        code=response or "",
        test_cases=cases,
        entry_point=str(item.get("entry_point") or ""),
        setup_code=str(item.get("setup_code") or ""),
        language=str(item.get("language") or "python"),
    )
    if result.compile_error:
        return False, result.compile_error, result.to_dict()

    edge_failed = [o.name for o in result.outcomes if not o.passed and o.is_edge_case]
    if result.all_passed:
        feedback = f"All {result.total} tests passed — including edge cases."
    else:
        feedback = f"{result.passed}/{result.total} tests passed."
        if edge_failed:
            feedback += f"\n\nEdge cases still failing: {', '.join(edge_failed[:4])}."
        first = next((o for o in result.outcomes if not o.passed), None)
        if first is not None:
            if first.error:
                feedback += f"\n\n{first.name} raised {first.error}"
            elif not first.hidden:
                feedback += (
                    f"\n\n{first.name}: expected {json.dumps(first.expected, default=str)}, "
                    f"got {json.dumps(first.actual, default=str)}"
                )
            if first.description:
                feedback += f"\n{first.description}"
    return result.all_passed, feedback, result.to_dict()
