"""Validate the authored coding-questions dataset under ``data/coding_questions/``.

Two jobs:

1. **Schema check** — every pack and question carries the fields the app loader
   needs (see ``docs/CODING_QUESTION_FORMAT.md``), ids are unique, every
   ``topic_id`` actually exists in ``data/notes/*.md``, and every question has at
   least one deliberate edge case with a ``teaches`` note.
2. **Execution check** — every reference ``solution`` is executed against every
   one of its ``test_cases`` in a subprocess. Any mismatch is a failure.

Usage (PowerShell — chain with ``;``):

    .venv\\Scripts\\python.exe scripts\\validate_coding_questions.py
    python scripts\\validate_coding_questions.py --python .venv\\Scripts\\python.exe
    python scripts\\validate_coding_questions.py --pack numpy_fundamentals --verbose

The parent process only needs the standard library; numpy/pandas/sklearn are
imported inside the child runner, so point ``--python`` at an interpreter that
has them (auto-detected from ``.venv`` when present).
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
QUESTIONS_DIR = ROOT / "data" / "coding_questions"
NOTES_DIR = ROOT / "data" / "notes"

SCHEMA_VERSION = "1.0"
DIFFICULTIES = {"easy", "medium", "hard"}
COMPARE_MODES = {
    "auto",
    "allclose",
    "repr",
    "strict",
    "frame",
    "series",
    "type_name",
    "unordered",
}
TOPIC_ID_RE = re.compile(r"^L\d+-T\d+$")
IDENT_RE = re.compile(r"^[a-z][a-z0-9_]*$")
QUESTION_ID_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")

PACK_KEYS = ("schema_version", "pack_id", "title", "domain", "language", "topic", "questions")
QUESTION_KEYS = (
    "id",
    "title",
    "topic",
    "difficulty",
    "language",
    "concept",
    "prompt",
    "starter_code",
    "solution",
    "entry_point",
    "test_cases",
    "explanation",
    "hints",
)
CASE_KEYS = ("name", "input", "expected", "is_edge_case", "teaches")


# --------------------------------------------------------------------------- #
# loading + schema
# --------------------------------------------------------------------------- #
def pack_paths(only: str | None = None) -> list[Path]:
    if not QUESTIONS_DIR.is_dir():
        return []
    out = []
    for path in sorted(QUESTIONS_DIR.glob("*.json")):
        if path.name.startswith("_") or path.name == "index.json":
            continue
        if only and path.stem != only:
            continue
        out.append(path)
    return out


def known_topic_ids() -> set[str]:
    found: set[str] = set()
    if not NOTES_DIR.is_dir():
        return found
    for note in NOTES_DIR.glob("*.md"):
        try:
            found.update(re.findall(r"L\d+-T\d+", note.read_text(encoding="utf-8")))
        except OSError:
            continue
    return found


def _check_case(case: Any, where: str) -> list[str]:
    errs: list[str] = []
    if not isinstance(case, dict):
        return [f"{where}: test case must be an object"]
    for key in CASE_KEYS:
        if key not in case:
            errs.append(f"{where}: missing '{key}'")
    if not str(case.get("name") or "").strip():
        errs.append(f"{where}: 'name' is empty")
    if not isinstance(case.get("is_edge_case"), bool):
        errs.append(f"{where}: 'is_edge_case' must be a bool")
    if len(str(case.get("teaches") or "").strip()) < 15:
        errs.append(f"{where}: 'teaches' must explain what the case reveals")
    payload = case.get("input")
    if not isinstance(payload, dict):
        errs.append(f"{where}: 'input' must be an object with 'args' / 'kwargs'")
    else:
        args = payload.get("args", [])
        kwargs = payload.get("kwargs", {})
        if not isinstance(args, list) or any(not isinstance(a, str) for a in args):
            errs.append(f"{where}: 'input.args' must be a list of Python expression strings")
        if not isinstance(kwargs, dict) or any(not isinstance(v, str) for v in kwargs.values()):
            errs.append(f"{where}: 'input.kwargs' values must be Python expression strings")
    if not isinstance(case.get("expected"), str):
        errs.append(f"{where}: 'expected' must be a Python expression string")
    kind = case.get("expected_kind", "value")
    if kind not in {"value", "raises"}:
        errs.append(f"{where}: 'expected_kind' must be 'value' or 'raises'")
    mode = case.get("compare", "auto")
    if mode not in COMPARE_MODES:
        errs.append(f"{where}: unknown compare mode {mode!r}")
    return errs


def _check_question(q: Any, where: str, topic_ids: set[str]) -> list[str]:
    errs: list[str] = []
    if not isinstance(q, dict):
        return [f"{where}: question must be an object"]
    for key in QUESTION_KEYS:
        if key not in q:
            errs.append(f"{where}: missing '{key}'")
    qid = str(q.get("id") or "")
    if not QUESTION_ID_RE.match(qid):
        errs.append(f"{where}: id {qid!r} must be lower-kebab-case")
    if q.get("difficulty") not in DIFFICULTIES:
        errs.append(f"{where}: difficulty must be one of {sorted(DIFFICULTIES)}")
    if q.get("language") != "python":
        errs.append(f"{where}: only language 'python' is authored today")
    if len(str(q.get("prompt") or "")) < 120:
        errs.append(f"{where}: 'prompt' must explain the concept, not just the task")
    if len(str(q.get("explanation") or "")) < 80:
        errs.append(f"{where}: 'explanation' is too thin")
    entry = str(q.get("entry_point") or "")
    if not IDENT_RE.match(entry):
        errs.append(f"{where}: entry_point {entry!r} must be a snake_case identifier")
    else:
        if f"def {entry}(" not in str(q.get("solution") or ""):
            errs.append(f"{where}: solution does not define {entry}()")
        if f"def {entry}(" not in str(q.get("starter_code") or ""):
            errs.append(f"{where}: starter_code does not declare {entry}()")
    if '"""' not in str(q.get("starter_code") or ""):
        errs.append(f"{where}: starter_code needs a docstring")
    hints = q.get("hints")
    if not isinstance(hints, list) or len(hints) < 2 or any(not str(h).strip() for h in hints):
        errs.append(f"{where}: 'hints' needs >= 2 progressive, non-empty hints")
    if q.get("hint") and hints and q["hint"] != hints[0]:
        errs.append(f"{where}: legacy 'hint' must mirror hints[0] for CodeDrill compatibility")
    tid = q.get("topic_id")
    if tid is not None:
        if not TOPIC_ID_RE.match(str(tid)):
            errs.append(f"{where}: topic_id {tid!r} must look like L5-T03")
        elif topic_ids and str(tid) not in topic_ids:
            errs.append(f"{where}: topic_id {tid!r} not found in data/notes/*.md")
    cases = q.get("test_cases")
    if not isinstance(cases, list) or len(cases) < 3:
        errs.append(f"{where}: needs >= 3 test cases")
        cases = cases if isinstance(cases, list) else []
    if not any(isinstance(c, dict) and c.get("is_edge_case") for c in cases):
        errs.append(f"{where}: needs >= 1 deliberate edge case")
    seen: set[str] = set()
    for i, case in enumerate(cases):
        errs.extend(_check_case(case, f"{where}/case[{i}]"))
        name = str(case.get("name") or "") if isinstance(case, dict) else ""
        if name in seen:
            errs.append(f"{where}/case[{i}]: duplicate case name {name!r}")
        seen.add(name)
    return errs


def check_schema(packs: list[tuple[Path, dict[str, Any]]]) -> list[str]:
    errs: list[str] = []
    topic_ids = known_topic_ids()
    seen_ids: dict[str, str] = {}
    for path, pack in packs:
        where = path.name
        for key in PACK_KEYS:
            if key not in pack:
                errs.append(f"{where}: pack missing '{key}'")
        if pack.get("schema_version") != SCHEMA_VERSION:
            errs.append(f"{where}: schema_version must be {SCHEMA_VERSION!r}")
        if pack.get("domain") != "coding":
            errs.append(f"{where}: domain must be 'coding'")
        if pack.get("pack_id") != path.stem:
            errs.append(f"{where}: pack_id must match the filename stem")
        questions = pack.get("questions")
        if not isinstance(questions, list) or not questions:
            errs.append(f"{where}: 'questions' must be a non-empty list")
            continue
        for q in questions:
            qid = str(q.get("id") or "?") if isinstance(q, dict) else "?"
            errs.extend(_check_question(q, f"{where}#{qid}", topic_ids))
            if qid in seen_ids:
                errs.append(f"{where}#{qid}: duplicate question id (also in {seen_ids[qid]})")
            seen_ids[qid] = where
    return errs


# --------------------------------------------------------------------------- #
# child runner: executes reference solutions against their test cases
# --------------------------------------------------------------------------- #
def _base_namespace() -> dict[str, Any]:
    import math

    ns: dict[str, Any] = {"math": math}
    for name, mod in (("np", "numpy"), ("pd", "pandas")):
        try:
            ns[name] = __import__(mod)
        except ImportError:
            pass
    return ns


def _missing_requirements(requires: list[str]) -> list[str]:
    missing = []
    for mod in requires:
        try:
            __import__(mod)
        except ImportError:
            missing.append(mod)
    return missing


def _assert_equal(got: Any, want: Any, mode: str) -> None:
    import math

    np = sys.modules.get("numpy")
    pd = sys.modules.get("pandas")

    if mode == "repr":
        assert repr(got) == repr(want), f"repr mismatch\n got: {got!r}\nwant: {want!r}"
        return
    if mode == "type_name":
        assert type(got).__name__ == want, f"type {type(got).__name__} != {want}"
        return
    if mode == "allclose":
        np.testing.assert_allclose(got, want, rtol=1e-7, atol=1e-9)
        return
    if mode == "strict":
        np.testing.assert_array_equal(got, want, strict=True)
        return
    if mode == "frame":
        pd.testing.assert_frame_equal(got, want)
        return
    if mode == "series":
        pd.testing.assert_series_equal(got, want)
        return
    if mode == "unordered":
        assert sorted(map(repr, got)) == sorted(map(repr, want)), (
            f"unordered mismatch\n got: {got!r}\nwant: {want!r}"
        )
        return

    # auto
    if pd is not None and isinstance(want, pd.DataFrame):
        pd.testing.assert_frame_equal(got, want)
        return
    if pd is not None and isinstance(want, pd.Series):
        pd.testing.assert_series_equal(got, want)
        return
    if pd is not None and isinstance(want, pd.Index):
        pd.testing.assert_index_equal(got, want)
        return
    if np is not None and isinstance(want, np.ndarray):
        if want.dtype.kind == "f":
            np.testing.assert_allclose(got, want, rtol=1e-7, atol=1e-9)
        else:
            np.testing.assert_array_equal(got, want)
        assert np.asarray(got).shape == want.shape, (
            f"shape {np.asarray(got).shape} != {want.shape}"
        )
        return
    if isinstance(want, (tuple, list)) and not isinstance(want, str):
        assert type(got) is type(want), f"container {type(got).__name__} != {type(want).__name__}"
        assert len(got) == len(want), f"length {len(got)} != {len(want)}"
        for g, w in zip(got, want):
            _assert_equal(g, w, "auto")
        return
    if isinstance(want, dict):
        assert set(got) == set(want), f"keys {sorted(map(str, got))} != {sorted(map(str, want))}"
        for key in want:
            _assert_equal(got[key], want[key], "auto")
        return
    if isinstance(want, float):
        if math.isnan(want):
            assert isinstance(got, float) and math.isnan(got), f"{got!r} is not nan"
            return
        assert math.isclose(float(got), want, rel_tol=1e-7, abs_tol=1e-9), f"{got!r} != {want!r}"
        return
    if isinstance(want, bool):
        assert bool(got) is want and isinstance(got, (bool,) + ((np.bool_,) if np else ())), (
            f"{got!r} is not the boolean {want!r}"
        )
        return
    assert got == want, f"{got!r} != {want!r}"


def run_pack(path: Path) -> dict[str, Any]:
    pack = json.loads(path.read_text(encoding="utf-8"))
    base = _base_namespace()
    results: list[dict[str, Any]] = []

    for q in pack.get("questions", []):
        entry = {"question_id": q.get("id"), "cases": [], "skipped": None}
        missing = _missing_requirements(list(q.get("requires") or []))
        if missing:
            entry["skipped"] = f"missing modules: {', '.join(missing)}"
            results.append(entry)
            continue

        solution_ns = dict(base)
        try:
            exec(compile(q["solution"], f"<{q['id']}:solution>", "exec"), solution_ns)  # noqa: S102
            fn = solution_ns[q["entry_point"]]
        except Exception as exc:  # noqa: BLE001
            entry["skipped"] = f"solution failed to load: {type(exc).__name__}: {exc}"
            results.append(entry)
            continue

        for case in q.get("test_cases", []):
            record = {"name": case.get("name"), "ok": False, "error": ""}
            try:
                # Inputs/expected are evaluated WITHOUT the solution in scope so an
                # expectation can never be defined in terms of the answer.
                eval_ns = dict(base)
                payload = case.get("input") or {}
                args = [eval(a, dict(eval_ns)) for a in payload.get("args", [])]  # noqa: S307
                kwargs = {
                    k: eval(v, dict(eval_ns))  # noqa: S307
                    for k, v in (payload.get("kwargs") or {}).items()
                }
                if case.get("expected_kind") == "raises":
                    want_exc = str(case["expected"])
                    try:
                        fn(*args, **kwargs)
                    except Exception as exc:  # noqa: BLE001
                        names = {c.__name__ for c in type(exc).__mro__}
                        if want_exc in names:
                            record["ok"] = True
                        else:
                            record["error"] = f"raised {type(exc).__name__}, expected {want_exc}"
                    else:
                        record["error"] = f"did not raise {want_exc}"
                else:
                    want = eval(case["expected"], dict(eval_ns))  # noqa: S307
                    got = fn(*args, **kwargs)
                    _assert_equal(got, want, case.get("compare", "auto"))
                    record["ok"] = True
            except Exception as exc:  # noqa: BLE001
                record["error"] = f"{type(exc).__name__}: {exc}".strip()[:600]
            entry["cases"].append(record)
        results.append(entry)

    return {"pack_id": pack.get("pack_id", path.stem), "results": results}


# --------------------------------------------------------------------------- #
# parent process
# --------------------------------------------------------------------------- #
def default_child_python() -> str:
    candidate = ROOT / ".venv" / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")
    return str(candidate) if candidate.exists() else sys.executable


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pack", help="validate a single pack by filename stem")
    parser.add_argument("--python", help="interpreter used to execute solutions")
    parser.add_argument("--verbose", action="store_true", help="list every passing case")
    parser.add_argument("--schema-only", action="store_true")
    parser.add_argument("--_run", help=argparse.SUPPRESS)
    args = parser.parse_args()

    if args._run:
        print(json.dumps(run_pack(Path(args._run))))
        return 0

    paths = pack_paths(args.pack)
    if not paths:
        print(f"no question packs found in {QUESTIONS_DIR}")
        return 1

    packs: list[tuple[Path, dict[str, Any]]] = []
    load_errors: list[str] = []
    for path in paths:
        try:
            packs.append((path, json.loads(path.read_text(encoding="utf-8"))))
        except json.JSONDecodeError as exc:
            load_errors.append(f"{path.name}: invalid JSON — {exc}")

    schema_errors = load_errors + check_schema(packs)
    print(f"packs: {len(packs)}  questions: {sum(len(p.get('questions', [])) for _, p in packs)}")
    if schema_errors:
        print(f"\nSCHEMA ERRORS ({len(schema_errors)}):")
        for err in schema_errors:
            print(f"  - {err}")
    else:
        print("schema: OK")

    if args.schema_only:
        return 1 if schema_errors else 0

    child = args.python or default_child_python()
    total = passed = failed = skipped = 0
    failures: list[str] = []

    for path, pack in packs:
        proc = subprocess.run(  # noqa: S603
            [child, str(Path(__file__).resolve()), "--_run", str(path)],
            capture_output=True,
            text=True,
        )
        if proc.returncode != 0 or not proc.stdout.strip():
            failures.append(f"{path.name}: runner crashed — {proc.stderr.strip()[:800]}")
            continue
        report = json.loads(proc.stdout)
        pack_pass = pack_fail = 0
        for entry in report["results"]:
            if entry.get("skipped"):
                skipped += 1
                failures.append(f"{path.name}#{entry['question_id']}: SKIPPED {entry['skipped']}")
                continue
            for case in entry["cases"]:
                total += 1
                if case["ok"]:
                    passed += 1
                    pack_pass += 1
                    if args.verbose:
                        print(f"  ok   {entry['question_id']} :: {case['name']}")
                else:
                    failed += 1
                    pack_fail += 1
                    failures.append(
                        f"{path.name}#{entry['question_id']} :: {case['name']}\n"
                        f"      {case['error']}"
                    )
        flag = "OK " if not pack_fail else "FAIL"
        print(f"{flag} {path.stem:<32} {pack_pass:>3} passed, {pack_fail:>3} failed")

    print("\n" + "=" * 70)
    print(f"test cases executed: {total}   passed: {passed}   failed: {failed}")
    if skipped:
        print(f"questions skipped (missing deps / broken solution): {skipped}")
    if failures:
        print(f"\nFAILURES ({len(failures)}):")
        for item in failures:
            print(f"  - {item}")
    if not failures and not schema_errors:
        print("ALL GREEN")
    print("=" * 70)
    return 1 if (failures or schema_errors) else 0


if __name__ == "__main__":
    raise SystemExit(main())
