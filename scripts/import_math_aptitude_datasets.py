"""Import aptitude datasets into data/questions/math/** for Daily Path / MT tags.

Sources (under data/math/imports/):
  - college_readiness/  — SAT-style MCQs
  - mathqa/             — MathQA word problems
  - hendrycks_math/     — MATH competition (filtered subjects)
  - saket-programming-aptitude/ — company coding-aptitude problem statements
  - mathgenerator/      — lukew3 procedural generators
  - mathematics_dataset/ — DeepMind generator source (HF deepmind/math_dataset used at import)
  - MathNet via HuggingFace ShadenA/MathNet (olympiad, answer-bearing subset)

Usage:
  python scripts/import_math_aptitude_datasets.py
  python scripts/import_math_aptitude_datasets.py --mathqa-limit 120 --mathgen-per 40 --mathnet-limit 400
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
from collections import defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
IMPORTS = ROOT / "data" / "math" / "imports"
OUT = ROOT / "data" / "questions" / "math"
NOTES = ROOT / "data" / "notes" / "math" / "MT1_aptitude_interview_notes.md"

# SAT domain / label → MT topic
SAT_DOMAIN_TO_MT = {
    "Algebra": ("MT1-T04", "math.aptitude.sat-algebra", "SAT Algebra"),
    "Advanced Math": ("MT2-T01", "math.aptitude.sat-advanced", "SAT Advanced Math"),
    "Problem-Solving and Data Analysis": ("MT1-T05", "math.aptitude.sat-data", "SAT Data Analysis"),
    "Geometry and Trigonometry": ("MT1-T14", "math.aptitude.sat-geometry", "SAT Geometry & Trig"),
}

MATHQA_CAT_TO_MT = {
    "gain": ("MT1-T08", "math.aptitude.mathqa-gain", "MathQA Profit / Gain"),
    "general": ("MT1-T03", "math.aptitude.mathqa-general", "MathQA General Quant"),
    "probability": ("MT1-T11", "math.aptitude.mathqa-probability", "MathQA Probability"),
    "geometry": ("MT1-T14", "math.aptitude.mathqa-geometry", "MathQA Geometry"),
    "physics": ("MT1-T06", "math.aptitude.mathqa-physics", "MathQA Rate / Physics Word Problems"),
    "other": ("MT1-T01", "math.aptitude.mathqa-other", "MathQA Mixed"),
}

MATH_SUBJECT_TO_MT = {
    "prealgebra": ("MT1-T01", "math.competition.prealgebra", "MATH Prealgebra"),
    "counting_and_probability": ("MT1-T11", "math.competition.counting-probability", "MATH Counting & Probability"),
    "algebra": ("MT2-T02", "math.competition.algebra", "MATH Algebra"),
    "number_theory": ("MT1-T01", "math.competition.number-theory", "MATH Number Theory"),
    "geometry": ("MT1-T14", "math.competition.geometry", "MATH Geometry"),
    "intermediate_algebra": ("MT2-T02", "math.competition.intermediate-algebra", "MATH Intermediate Algebra"),
    "precalculus": ("MT2-T01", "math.competition.precalculus", "MATH Precalculus"),
}


def _clip(s: str, n: int = 4000) -> str:
    s = (s or "").strip()
    return s if len(s) <= n else s[: n - 1] + "…"


def _write_topic(
    *,
    rel_path: str,
    topic_id: str,
    title: str,
    note_topic_ids: list[str],
    track: str,
    stage: str,
    path: list[str],
    description: str,
    questions: list[dict[str, Any]],
) -> Path:
    out = OUT / rel_path
    out.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": 1,
        "kind": "math",
        "topic": {
            "topic_id": topic_id,
            "title": title,
            "stage": stage,
            "path": path,
            "track": track,
            "prerequisites": [],
            "note_topic_ids": note_topic_ids,
            "description": description,
        },
        "questions": questions,
    }
    out.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return out


def _parse_mathqa_options(raw: str) -> list[tuple[str, str]]:
    """Parse 'a ) 140 , b ) 130 , c ) 120' → [('a','140'), ...]."""
    text = (raw or "").strip()
    parts = re.split(r"(?i)\s*([a-e])\s*\)\s*", text)
    out: list[tuple[str, str]] = []
    if len(parts) > 1:
        for i in range(1, len(parts), 2):
            letter = parts[i].lower()
            val = parts[i + 1].strip(" ,;") if i + 1 < len(parts) else ""
            if letter and val:
                out.append((letter, val))
    return out


def import_college_readiness() -> int:
    path = IMPORTS / "college_readiness" / "College Readiness Math Questions Dataset_train.json"
    if not path.exists():
        print("skip college_readiness: missing", path)
        return 0
    rows = json.loads(path.read_text(encoding="utf-8"))
    buckets: dict[str, list[dict[str, Any]]] = defaultdict(list)
    meta: dict[str, tuple[str, str, str]] = {}
    for row in rows:
        domain = str(row.get("domain") or "Algebra")
        mt, tid, title = SAT_DOMAIN_TO_MT.get(domain, SAT_DOMAIN_TO_MT["Algebra"])
        meta[tid] = (mt, title, domain)
        opts = [
            str(row.get("choice_A") or ""),
            str(row.get("choice_B") or ""),
            str(row.get("choice_C") or ""),
            str(row.get("choice_D") or ""),
        ]
        letter = str(row.get("correct_answer") or "A").strip().upper()[:1]
        idx = ord(letter) - ord("A") if letter in "ABCD" else 0
        answer = opts[idx] if 0 <= idx < len(opts) else letter
        lines = [str(row.get("question") or "").strip(), "", "Options:"]
        for i, o in enumerate(opts):
            if o:
                lines.append(f"{chr(65 + i)}) {o}")
        buckets[tid].append(
            {
                "id": f"{tid}.q{len(buckets[tid]) + 1:04d}",
                "problem": _clip("\n".join(lines)),
                "answer": _clip(answer, 200),
                "answer_format": "text",
                "difficulty": "medium",
                "solution_steps": [],
                "explanation": _clip(str(row.get("question_comments") or ""), 500),
                "hint": f"Skill: {row.get('label') or domain}",
                "tags": ["sat", "college-readiness", str(row.get("label") or "").lower().replace(" ", "-")],
            }
        )
    n = 0
    for tid, qs in buckets.items():
        mt, title, domain = meta[tid]
        _write_topic(
            rel_path=f"aptitude/sat/{tid.split('.')[-1]}.json",
            topic_id=tid,
            title=title,
            note_topic_ids=[mt],
            track="aptitude",
            stage="foundations",
            path=["Aptitude", "SAT", domain],
            description=f"College Readiness / SAT-style items ({domain}).",
            questions=qs,
        )
        n += len(qs)
        print(f"  sat {tid}: {len(qs)}")
    return n


def import_mathqa(*, limit_per_cat: int) -> int:
    path = IMPORTS / "mathqa" / "train.json"
    if not path.exists():
        # sometimes nested
        hits = list((IMPORTS / "mathqa").rglob("train.json"))
        path = hits[0] if hits else path
    if not path.exists():
        print("skip mathqa: missing train.json")
        return 0
    # Also pull dev/test if present (more coverage)
    paths = [path]
    for name in ("dev.json", "test.json"):
        for hit in (IMPORTS / "mathqa").rglob(name):
            if hit not in paths:
                paths.append(hit)
    rows: list[Any] = []
    for p in paths:
        try:
            chunk = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(chunk, list):
            rows.extend(chunk)
    buckets: dict[str, list[dict[str, Any]]] = defaultdict(list)
    meta: dict[str, tuple[str, str, str]] = {}
    counts: dict[str, int] = defaultdict(int)
    unlimited = limit_per_cat <= 0
    for i, row in enumerate(rows):
        cat = str(row.get("category") or "other").lower()
        if cat not in MATHQA_CAT_TO_MT:
            cat = "other"
        if not unlimited and counts[cat] >= limit_per_cat:
            continue
        mt, tid, title = MATHQA_CAT_TO_MT[cat]
        meta[tid] = (mt, title, cat)
        options = _parse_mathqa_options(str(row.get("options") or ""))
        correct = str(row.get("correct") or "a").strip().lower()[:1]
        answer = next((v for L, v in options if L == correct), correct)
        lines = [str(row.get("Problem") or "").strip(), ""]
        if options:
            lines.append("Options:")
            for L, v in options:
                lines.append(f"{L.upper()}) {v}")
        rationale = str(row.get("Rationale") or "").strip()
        buckets[tid].append(
            {
                "id": f"{tid}.q{counts[cat] + 1:04d}",
                "problem": _clip("\n".join(lines)),
                "answer": _clip(str(answer), 200),
                "answer_format": "text",
                "difficulty": "medium",
                "solution_steps": [s.strip() for s in re.split(r"(?<=[.])\s+", rationale) if s.strip()][:8]
                if rationale
                else [],
                "explanation": _clip(rationale, 800),
                "hint": f"MathQA category: {cat}",
                "tags": ["mathqa", cat],
            }
        )
        counts[cat] += 1
    n = 0
    for tid, qs in buckets.items():
        mt, title, cat = meta[tid]
        _write_topic(
            rel_path=f"aptitude/mathqa/{cat}.json",
            topic_id=tid,
            title=title,
            note_topic_ids=[mt],
            track="aptitude",
            stage="foundations",
            path=["Aptitude", "MathQA", cat],
            description=f"MathQA word problems ({cat}).",
            questions=qs,
        )
        n += len(qs)
        print(f"  mathqa {cat}: {len(qs)}")
    return n


def import_hendrycks(*, limit_per_subject: int, max_level: int, include_test: bool = True) -> int:
    base = IMPORTS / "hendrycks_math" / "MATH"
    if not base.exists():
        hits = list((IMPORTS / "hendrycks_math").rglob("MATH"))
        base = next((h for h in hits if h.is_dir()), base)
    splits = ["train"]
    if include_test:
        splits.append("test")
    roots = [base / s for s in splits if (base / s).is_dir()]
    if not roots:
        print("skip hendrycks: missing MATH/train")
        return 0
    unlimited = limit_per_subject <= 0
    n = 0
    for subject, (mt, tid, title) in MATH_SUBJECT_TO_MT.items():
        qs: list[dict[str, Any]] = []
        files: list[Path] = []
        for root in roots:
            folder = root / subject
            if folder.is_dir():
                files.extend(sorted(folder.glob("*.json")))
        for fp in files:
            if not unlimited and len(qs) >= limit_per_subject:
                break
            row = json.loads(fp.read_text(encoding="utf-8"))
            try:
                level = int(str(row.get("level") or "1").replace("Level", "").strip() or "1")
            except ValueError:
                level = 1
            if level > max_level:
                continue
            problem = str(row.get("problem") or "").strip()
            solution = str(row.get("solution") or "").strip()
            m = re.search(r"\\boxed\{([^{}]+)\}", solution)
            if m:
                answer = m.group(1).strip()
                answer_format = "expression"
                tags = ["hendrycks-math", subject, f"level-{level}"]
            else:
                answer = ""
                answer_format = "open"
                tags = ["hendrycks-math", subject, f"level-{level}", "no-answer", "open"]
            qs.append(
                {
                    "id": f"{tid}.q{len(qs) + 1:04d}",
                    "problem": _clip(problem),
                    "answer": _clip(answer, 300),
                    "answer_format": answer_format,
                    "difficulty": "easy" if level <= 2 else "medium" if level <= 3 else "hard",
                    "solution_steps": [s.strip() for s in solution.split("\n") if s.strip()][:12],
                    "explanation": _clip(solution, 1000),
                    "hint": f"MATH {subject} level {level}",
                    "tags": tags,
                }
            )
        if not qs:
            continue
        _write_topic(
            rel_path=f"competition/{subject}.json",
            topic_id=tid,
            title=title,
            note_topic_ids=[mt],
            track="aiml" if subject in {"algebra", "intermediate_algebra", "precalculus"} else "aptitude",
            stage="core" if subject in {"algebra", "intermediate_algebra"} else "foundations",
            path=["Math", "Competition", subject.replace("_", " ")],
            description=f"Hendrycks MATH {subject} (level ≤ {max_level}, train+test).",
            questions=qs,
        )
        n += len(qs)
        print(f"  math/{subject}: {len(qs)}")
    return n


_SAMPLE_OUT = re.compile(
    r"(?is)(?:sample\s*output|expected\s*(?:result\s*)?(?:value|output)|output)\s*[:\-]?\s*(.+?)(?:\n\s*\n|\Z)"
)
_SAMPLE_IN = re.compile(
    r"(?is)(?:sample\s*input|input)\s*[:\-]?\s*(.+?)(?=(?:sample\s*output|expected|output)\s*[:\-]|\Z)"
)


def import_saket(*, limit: int) -> int:
    root = IMPORTS / "saket-programming-aptitude"
    if not root.exists():
        print("skip saket: missing clone")
        return 0
    statements = sorted(root.rglob("Problem Statement.txt"))
    # Also pick up .txt/.md problem files in company folders
    extra = [
        p
        for p in root.rglob("*")
        if p.is_file()
        and p.suffix.lower() in {".txt", ".md"}
        and "problem" in p.name.lower()
        and p.name.lower() != "problem statement.txt"
    ]
    files = statements + sorted(extra)
    unlimited = limit <= 0
    by_company: dict[str, list[dict[str, Any]]] = defaultdict(list)
    total = 0
    for fp in files:
        if not unlimited and total >= limit:
            break
        text = fp.read_text(encoding="utf-8", errors="replace").strip()
        if len(text) < 40:
            continue
        # company ≈ folder under saket root
        try:
            rel = fp.relative_to(root)
            company = rel.parts[0] if rel.parts else "interview"
        except ValueError:
            company = "interview"
        folder = fp.parent.name
        out_m = _SAMPLE_OUT.search(text)
        in_m = _SAMPLE_IN.search(text)
        answer = ""
        if out_m:
            answer = out_m.group(1).strip().splitlines()[0].strip()
        if not answer:
            m2 = re.search(r"(?im)^output\s*[:\-]?\s*(\S+)", text)
            if m2:
                answer = m2.group(1).strip()
        tags = ["saket", "programming-aptitude", company.lower().replace(" ", "-")]
        answer_format = "text"
        if not answer:
            answer_format = "open"
            tags.extend(["no-answer", "open"])
        hint = ""
        if in_m:
            hint = "Sample input: " + _clip(in_m.group(1).strip().replace("\n", " | "), 160)
        slug = re.sub(r"[^a-z0-9]+", "-", company.lower()).strip("-") or "interview"
        tid = f"math.aptitude.saket-{slug}"
        by_company[tid].append(
            {
                "id": f"{tid}.q{len(by_company[tid]) + 1:04d}",
                "problem": _clip(
                    f"**{company} · {folder}**\n\n{text}\n\n"
                    "(Programming aptitude — implement the described function / logic.)"
                ),
                "answer": _clip(answer, 200),
                "answer_format": answer_format,
                "difficulty": "medium",
                "solution_steps": [],
                "explanation": "Sourced from SAKET-SK/Programming-Aptitude-Interview-Prep.",
                "hint": hint or "Trace the sample carefully; watch null / edge cases.",
                "tags": tags,
                "_company": company,
            }
        )
        total += 1
    n = 0
    for tid, qs in by_company.items():
        company = str(qs[0].get("_company") or "interview")
        cleaned = []
        for q in qs:
            q = dict(q)
            q.pop("_company", None)
            cleaned.append(q)
        slug = tid.split("saket-")[-1]
        _write_topic(
            rel_path=f"aptitude/saket/{slug}.json",
            topic_id=tid,
            title=f"Programming aptitude — {company}",
            note_topic_ids=["MT1-T13"],
            track="aptitude",
            stage="foundations",
            path=["Aptitude", "SAKET", company],
            description=f"Interview coding aptitude from {company}.",
            questions=cleaned,
        )
        n += len(cleaned)
        print(f"  saket {company}: {len(cleaned)}")
    return n


# lukew3/mathgenerator ids → (MT tag, topic slug, title, per-gen count)
MATHGEN_MAP: list[tuple[int, str, str, str]] = [
    # (gen_id, MT, topic_id, title) — ids verified against mathgenerator._gen_list
    (9, "MT1-T02", "math.aptitude.gen-lcm", "Generated LCM"),
    (120, "MT1-T02", "math.aptitude.gen-gcd", "Generated GCD"),
    (40, "MT1-T02", "math.aptitude.gen-common-factors", "Generated common factors"),
    (27, "MT1-T01", "math.aptitude.gen-prime-factors", "Generated prime factors"),
    (80, "MT1-T03", "math.aptitude.gen-percentage", "Generated percentages"),
    (63, "MT1-T08", "math.aptitude.gen-profit-loss", "Generated profit/loss %"),
    (45, "MT1-T09", "math.aptitude.gen-simple-interest", "Generated simple interest"),
    (78, "MT1-T09", "math.aptitude.gen-compound-interest", "Generated compound interest"),
    (30, "MT1-T10", "math.aptitude.gen-combinations", "Generated combinations"),
    (42, "MT1-T10", "math.aptitude.gen-permutations", "Generated permutations"),
    (52, "MT1-T11", "math.aptitude.gen-dice-prob", "Generated dice probability"),
    (82, "MT1-T12", "math.aptitude.gen-ap-term", "Generated AP term"),
    (83, "MT1-T12", "math.aptitude.gen-ap-sum", "Generated AP sum"),
    (66, "MT1-T12", "math.aptitude.gen-gp", "Generated geometric progression"),
    (11, "MT2-T01", "math.aptitude.gen-basic-algebra", "Generated basic algebra"),
    (26, "MT2-T01", "math.aptitude.gen-linear-eq", "Generated linear equations"),
    (50, "MT2-T01", "math.aptitude.gen-quadratic", "Generated quadratic equations"),
    (72, "MT3-T01", "math.aiml.gen-vector-dot", "Generated vector dot product"),
    (43, "MT3-T01", "math.aiml.gen-vector-cross", "Generated vector cross product"),
]


def import_mathgenerator(*, per_gen: int) -> int:
    """Generate fresh school/interview-style items via lukew3/mathgenerator."""
    import sys

    mg_root = IMPORTS / "mathgenerator"
    if not mg_root.exists():
        print("skip mathgenerator: missing clone")
        return 0
    sys.path.insert(0, str(mg_root))
    try:
        import mathgenerator as mg
    except Exception as exc:  # noqa: BLE001
        print("skip mathgenerator: import failed", exc)
        return 0

    buckets: dict[str, list[dict[str, Any]]] = defaultdict(list)
    meta: dict[str, tuple[str, str]] = {}
    n = 0
    for gen_id, mt, tid, title in MATHGEN_MAP:
        meta[tid] = (mt, title)
        for i in range(per_gen):
            try:
                problem, answer = mg.gen_by_id(gen_id)
            except Exception:  # noqa: BLE001
                continue
            problem = str(problem).strip()
            answer = str(answer).strip().strip("$")
            if not problem or not answer or problem.upper() == "DELETED":
                continue
            buckets[tid].append(
                {
                    "id": f"{tid}.q{len(buckets[tid]) + 1:04d}",
                    "problem": _clip(problem),
                    "answer": _clip(answer, 200),
                    "answer_format": "expression",
                    "difficulty": "easy",
                    "solution_steps": [],
                    "explanation": f"Generated by mathgenerator id={gen_id}.",
                    "hint": title,
                    "tags": ["mathgenerator", f"gen-{gen_id}"],
                }
            )
            n += 1
    for tid, qs in buckets.items():
        if not qs:
            continue
        mt, title = meta[tid]
        folder = "aiml" if mt.startswith("MT3") or mt.startswith("MT4") else "generated"
        _write_topic(
            rel_path=f"{folder}/{tid.split('.')[-1]}.json",
            topic_id=tid,
            title=title,
            note_topic_ids=[mt],
            track="aptitude" if mt.startswith("MT1") or mt.startswith("MT2") else "aiml",
            stage="foundations",
            path=["Aptitude", "Generated", title] if folder == "generated" else ["AI/ML", "Generated", title],
            description="Procedurally generated via lukew3/mathgenerator.",
            questions=qs,
        )
        print(f"  mathgen {tid}: {len(qs)}")
    return n


DEEPMIND_MODULES = [
    # (module name in train flat dict, MT, topic_id, title)
    ("arithmetic__add_or_sub", "MT1-T01", "math.aptitude.dm-add-sub", "DeepMind add/sub"),
    ("arithmetic__mul", "MT1-T01", "math.aptitude.dm-mul", "DeepMind multiplication"),
    ("arithmetic__div", "MT1-T01", "math.aptitude.dm-div", "DeepMind division"),
    ("numbers__gcd", "MT1-T02", "math.aptitude.dm-gcd", "DeepMind GCD"),
    ("numbers__lcm", "MT1-T02", "math.aptitude.dm-lcm", "DeepMind LCM"),
    ("arithmetic__nearest_integer_root", "MT1-T01", "math.aptitude.dm-root", "DeepMind roots"),
    ("algebra__linear_1d", "MT2-T01", "math.aptitude.dm-linear-1d", "DeepMind linear 1D"),
    ("probability__swr_p_level_set", "MT1-T11", "math.aptitude.dm-prob", "DeepMind probability"),
]


def import_deepmind(*, limit_per_config: int) -> int:
    """Generate school-level Q/A via local google-deepmind/mathematics_dataset clone."""
    import sys

    dm_root = IMPORTS / "mathematics_dataset"
    if not dm_root.exists():
        print("skip deepmind: missing clone")
        return 0
    sys.path.insert(0, str(dm_root))
    try:
        from absl import flags
        from mathematics_dataset.generate import filtered_modules, init_modules, sample_from_module

        # absl flags must be parsed before init_modules reads FLAGS.*
        if not flags.FLAGS.is_parsed():
            flags.FLAGS([sys.argv[0]])
        init_modules()
        flat = filtered_modules.get("train") or {}
    except Exception as exc:  # noqa: BLE001
        print("skip deepmind: init failed", exc)
        return 0

    n = 0
    for mod_name, mt, tid, title in DEEPMIND_MODULES:
        module = flat.get(mod_name)
        if module is None:
            print(f"  deepmind skip {mod_name}: not in train modules")
            continue
        qs: list[dict[str, Any]] = []
        for _ in range(limit_per_config * 3):
            if len(qs) >= limit_per_config:
                break
            try:
                problem, _dropped = sample_from_module(module)
            except Exception:  # noqa: BLE001
                continue
            q = str(problem.question).strip()
            a = str(problem.answer).strip()
            if not q or not a:
                continue
            qs.append(
                {
                    "id": f"{tid}.q{len(qs) + 1:04d}",
                    "problem": _clip(q),
                    "answer": _clip(a, 200),
                    "answer_format": "expression",
                    "difficulty": "easy",
                    "solution_steps": [],
                    "explanation": f"DeepMind mathematics_dataset · {mod_name}",
                    "hint": title,
                    "tags": ["deepmind", "mathematics_dataset", mod_name],
                }
            )
        if not qs:
            print(f"  deepmind {mod_name}: 0")
            continue
        _write_topic(
            rel_path=f"deepmind/{mod_name.replace('__', '_')}.json",
            topic_id=tid,
            title=title,
            note_topic_ids=[mt],
            track="aptitude",
            stage="foundations",
            path=["Aptitude", "DeepMind", mod_name],
            description=f"google-deepmind/mathematics_dataset ({mod_name}).",
            questions=qs,
        )
        n += len(qs)
        print(f"  deepmind {mod_name}: {len(qs)}")
    return n


def import_mathnet(*, limit: int, english_only: bool = True, require_answer: bool = False) -> int:
    """Import English MathNet problems. Includes proof/open items without final answers."""
    try:
        from datasets import load_dataset
    except ImportError:
        print("skip mathnet: pip install datasets")
        return 0

    try:
        ds = load_dataset("ShadenA/MathNet", split="train", streaming=True)
    except Exception as exc:  # noqa: BLE001
        print("skip mathnet:", exc)
        return 0

    topic_buckets: dict[str, list[dict[str, Any]]] = defaultdict(list)
    seen = 0
    for row in ds:
        if sum(len(v) for v in topic_buckets.values()) >= limit:
            break
        seen += 1
        if seen > limit * 40:
            # safety if almost nothing matches language filters
            break
        if english_only and str(row.get("language") or "").lower() not in ("en", "english", ""):
            lang = str(row.get("language") or "").lower()
            if lang and lang not in ("en", "english"):
                continue
        final_raw = row.get("final_answer")
        final = "" if final_raw is None else str(final_raw).strip()
        if final.lower() in ("null", "none"):
            final = ""
        if require_answer and not final:
            continue
        problem = str(row.get("problem_markdown") or "").strip()
        if not problem or len(problem) < 20:
            continue
        topics = row.get("topics_flat") or []
        topic0 = str(topics[0]) if topics else "Algebra"
        top = topic0.split(">")[0].strip().lower()
        if "number" in top:
            mt, tid, title = "MT1-T01", "math.olympiad.mathnet-number", "MathNet Number Theory"
        elif "combin" in top or "count" in top:
            mt, tid, title = "MT1-T10", "math.olympiad.mathnet-combinatorics", "MathNet Combinatorics"
        elif "probab" in top:
            mt, tid, title = "MT1-T11", "math.olympiad.mathnet-probability", "MathNet Probability"
        elif "algebra" in top:
            mt, tid, title = "MT2-T02", "math.olympiad.mathnet-algebra", "MathNet Algebra"
        elif "calculus" in top or "analys" in top:
            mt, tid, title = "MT4-T01", "math.olympiad.mathnet-calculus", "MathNet Calculus"
        elif "geometry" in top:
            mt, tid, title = "MT1-T14", "math.olympiad.mathnet-geometry", "MathNet Geometry"
        else:
            mt, tid, title = "MT2-T02", "math.olympiad.mathnet-mixed", "MathNet Mixed"
        sols = row.get("solutions_markdown") or []
        sol0 = str(sols[0]) if sols else ""
        tags = ["mathnet", str(row.get("country") or "").lower().replace(" ", "-")]
        if not final:
            tags.append("no-answer")
            tags.append("open")
        topic_buckets[tid].append(
            {
                "id": f"{tid}.q{len(topic_buckets[tid]) + 1:04d}",
                "problem": _clip(problem, 5000),
                "answer": _clip(final, 300) if final else "",
                "answer_format": "expression" if final else "open",
                "difficulty": "hard",
                "solution_steps": [s.strip() for s in sol0.split("\n") if s.strip()][:10],
                "explanation": _clip(sol0, 1500),
                "hint": f"{row.get('competition') or ''} · {topic0}",
                "tags": tags,
                "_mt": mt,
                "_title": title,
            }
        )

    n = 0
    open_n = 0
    for tid, qs in topic_buckets.items():
        if not qs:
            continue
        mt = str(qs[0].get("_mt") or "MT2-T02")
        title = str(qs[0].get("_title") or tid)
        cleaned = []
        for q in qs:
            q = dict(q)
            q.pop("_mt", None)
            q.pop("_title", None)
            if not (q.get("answer") or "").strip():
                open_n += 1
            cleaned.append(q)
        _write_topic(
            rel_path=f"olympiad/mathnet/{tid.split('.')[-1]}.json",
            topic_id=tid,
            title=title,
            note_topic_ids=[mt],
            track="aiml",
            stage="advanced",
            path=["Math", "Olympiad", "MathNet", title],
            description="ShadenA/MathNet olympiad problems (with or without final answers).",
            questions=cleaned,
        )
        n += len(cleaned)
        print(f"  mathnet {tid}: {len(cleaned)}")
    print(f"  mathnet open/no-answer: {open_n}")
    return n


def ensure_mt1_t13_note() -> None:
    if not NOTES.exists():
        return
    text = NOTES.read_text(encoding="utf-8")
    if "MT1-T13" in text:
        return
    text = text.replace(
        "- `MT1-T12` — Progressions (AP / GP)\n",
        "- `MT1-T12` — Progressions (AP / GP)\n"
        "- `MT1-T13` — Programming aptitude (interview coding rounds)\n",
    )
    block = """

## `MT1-T13` — Programming aptitude (interview coding rounds)

**What it is:** Short coding-round problems (carries, replacements, rate/food, divisibility sums) common in Accenture/TCS-style on-campus tests — logic first, language second.

**Remember:** Always handle null/empty inputs and off-by-one on inclusive ranges. Translate the sample before writing code.

**Takeaway:** These sit beside quant aptitude in Daily Path: read the pattern → implement → check the sample output.

"""
    if "## Open Items" in text:
        text = text.replace("## Open Items", block + "## Open Items")
    else:
        text += block
    NOTES.write_text(text, encoding="utf-8")
    print("  updated MT1 notes with T13")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mathqa-limit", type=int, default=150, help="Per category; 0 = all")
    parser.add_argument("--math-limit", type=int, default=100, help="Per MATH subject; 0 = all")
    parser.add_argument("--math-max-level", type=int, default=3)
    parser.add_argument("--saket-limit", type=int, default=120, help="0 = all problem statements")
    parser.add_argument("--mathgen-per", type=int, default=40, help="Problems per mathgenerator id")
    parser.add_argument("--deepmind-limit", type=int, default=80)
    parser.add_argument("--mathnet-limit", type=int, default=400)
    parser.add_argument(
        "--full",
        action="store_true",
        help="Large multi-source import (MathQA/MATH/SAKET/MathNet/DeepMind raised caps)",
    )
    parser.add_argument(
        "--mathnet-require-answer",
        action="store_true",
        help="Skip MathNet rows without final_answer (default: keep open/proof problems)",
    )
    parser.add_argument("--mathnet-only", action="store_true", help="Only re-import MathNet packs")
    parser.add_argument("--skip-deepmind", action="store_true")
    parser.add_argument("--skip-mathnet", action="store_true")
    parser.add_argument("--clean-out", action="store_true", help="Remove existing data/questions/math first")
    args = parser.parse_args()

    if args.full:
        if args.mathqa_limit == 150:
            args.mathqa_limit = 0
        if args.math_limit == 100:
            args.math_limit = 0
        if args.math_max_level == 3:
            args.math_max_level = 5
        if args.saket_limit == 120:
            args.saket_limit = 0
        if args.mathgen_per == 40:
            args.mathgen_per = 60
        if args.deepmind_limit == 80:
            args.deepmind_limit = 200
        if args.mathnet_limit == 400:
            args.mathnet_limit = 5000

    if args.clean_out and OUT.exists():
        # Keep curriculum + authored packs
        keep = []
        for rel in ("curriculum.json", "aptitude/authored"):
            p = OUT / rel
            if p.exists():
                keep.append(p)
        shutil.rmtree(OUT)
        OUT.mkdir(parents=True, exist_ok=True)
        # authored restored only if we copied — simpler: don't delete authored
    OUT.mkdir(parents=True, exist_ok=True)

    print("Importing aptitude datasets ->", OUT)
    if args.full:
        print(
            "  mode=full",
            f"mathqa={args.mathqa_limit}",
            f"math={args.math_limit}",
            f"level≤{args.math_max_level}",
            f"saket={args.saket_limit}",
            f"mathnet={args.mathnet_limit}",
            f"deepmind={args.deepmind_limit}",
            f"mathgen/={args.mathgen_per}",
        )
    total = 0
    if args.mathnet_only:
        mathnet_dir = OUT / "olympiad" / "mathnet"
        if mathnet_dir.exists():
            shutil.rmtree(mathnet_dir)
        total += import_mathnet(
            limit=args.mathnet_limit,
            require_answer=args.mathnet_require_answer,
        )
    else:
        total += import_college_readiness()
        total += import_mathqa(limit_per_cat=args.mathqa_limit)
        total += import_hendrycks(
            limit_per_subject=args.math_limit,
            max_level=args.math_max_level,
            include_test=True,
        )
        # Replace old single saket file if present
        old_saket = OUT / "aptitude" / "saket" / "programming-aptitude.json"
        if old_saket.exists():
            old_saket.unlink()
        total += import_saket(limit=args.saket_limit)
        total += import_mathgenerator(per_gen=args.mathgen_per)
        if not args.skip_deepmind:
            total += import_deepmind(limit_per_config=args.deepmind_limit)
        if not args.skip_mathnet:
            total += import_mathnet(
                limit=args.mathnet_limit,
                require_answer=args.mathnet_require_answer,
            )
        ensure_mt1_t13_note()
    print("TOTAL questions written:", total)

    import sys

    sys.path.insert(0, str(ROOT))
    from backend.quiz.content_bank import load_catalog

    cat = load_catalog(refresh=True)
    print(
        "content_bank:",
        cat.to_dict()["topic_count"],
        "topics,",
        cat.to_dict()["question_count"],
        "questions, errors=",
        len(cat.errors),
    )
    for err in cat.errors[:8]:
        print("  ERR", err)
    return 0 if not cat.errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
