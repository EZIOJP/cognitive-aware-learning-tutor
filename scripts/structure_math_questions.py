"""Retag geometry packs, add MT1-T07 bank, move aiml files, rewrite curriculum."""
from __future__ import annotations

import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MATH_Q = ROOT / "data" / "questions" / "math"

GEOM_RETAG = {
    "math.aptitude.sat-geometry": "MT1-T14",
    "math.aptitude.mathqa-geometry": "MT1-T14",
    "math.olympiad.mathnet-geometry": "MT1-T14",
}


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _dump(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def retag_geometry() -> None:
    for path in MATH_Q.rglob("*.json"):
        if path.name == "curriculum.json":
            continue
        data = _load(path)
        tid = (data.get("topic") or {}).get("topic_id")
        if tid not in GEOM_RETAG:
            continue
        data["topic"]["note_topic_ids"] = [GEOM_RETAG[tid]]
        if "Geometry" not in data["topic"].get("title", ""):
            pass
        _dump(path, data)
        print(f"retag {tid} → {GEOM_RETAG[tid]}")


def move_aiml() -> None:
    aiml = MATH_Q / "aiml"
    aiml.mkdir(parents=True, exist_ok=True)
    for name in ("gen-vector-dot.json", "gen-vector-cross.json"):
        src = MATH_Q / "generated" / name
        if not src.exists():
            continue
        dst = aiml / name
        shutil.move(str(src), str(dst))
        print(f"move {src.relative_to(MATH_Q)} → aiml/{name}")


def write_time_work() -> None:
    """Classic interview time & work — closed-form numeric answers."""
    # (problem, answer, difficulty, hint)
    rows: list[tuple[str, str, str, str]] = [
        ("A can finish a job in 10 days. How much of the job does A do in 1 day?", "1/10", "easy", "rate = 1/days"),
        ("A finishes a job in 12 days and B in 18 days. In how many days do they finish together?", "36/5", "easy", "1/12+1/18"),
        ("A finishes in 8 days, B in 12 days. Days together?", "24/5", "easy", "add rates"),
        ("A can do a job in 15 days. B is twice as fast as A. Days for B alone?", "15/2", "easy", "twice as fast → half the time"),
        ("A and B together finish in 6 days. A alone takes 10 days. Days for B alone?", "15", "easy", "1/B = 1/6 - 1/10"),
        ("A, B, C rates are 1/5, 1/10, 1/15 of a job per day. Days all three together?", "30/11", "medium", "sum rates"),
        ("A does a job in 20 days. After 5 days B joins and they finish in 5 more days. Days for B alone?", "20", "medium", "A works 10 days total"),
        ("Pipe A fills a tank in 4 hours, pipe B in 6 hours. Hours to fill together?", "12/5", "easy", "filling rates add"),
        ("Pipe A fills in 5 h, B empties in 10 h. Hours to fill if both open?", "10", "medium", "1/5 - 1/10"),
        ("Two pipes fill a tank in 10 and 15 minutes. Minutes together?", "6", "easy", "1/10+1/15"),
        ("A is thrice as efficient as B. Together they finish in 12 days. Days for A alone?", "16", "medium", "rates 3k and k"),
        ("A and B together take 8 days; A alone takes 12. Days for B?", "24", "easy", "1/B=1/8-1/12"),
        ("6 men finish a job in 10 days. Days for 15 men (same rate)?", "4", "easy", "man-days constant"),
        ("12 women finish in 8 days. Days for 8 women?", "12", "easy", "man-days"),
        ("A takes 5 days more than B; together 6 days. Days for B alone?", "10", "hard", "1/(x+5)+1/x=1/6"),
        ("A takes 4 days less than B; together 24/7 days. Days for A?", "6", "hard", "let B=x, A=x-4"),
        ("Work done by A in 3 days equals B in 4 days. If A finishes alone in 20 days, days for B?", "80/3", "medium", "rates proportional"),
        ("A can do 1/3 of a job in 5 days. Days for full job alone?", "15", "easy", "scale up"),
        ("B can do 40% of a job in 8 days. Days for full job?", "20", "easy", "0.4 in 8 → 1 in 20"),
        ("A and B take 9 and 12 days. They work alternate days starting with A. Days to finish?", "10", "hard", "2-day cycle = 1/9+1/12"),
        ("3 taps fill a cistern in 12, 15, 20 minutes. Minutes all open?", "5", "medium", "1/12+1/15+1/20"),
        ("A leak empties a full tank in 20 h. Filling pipe alone fills empty tank in 5 h. Hours with both?", "20/3", "medium", "1/5-1/20"),
        ("20 workers finish in 15 days. After 5 days, 5 leave. Extra days for remaining?", "40/3", "hard", "remaining work after 5 days"),
        ("A+B=10 days, B+C=12 days, C+A=15 days. Days for A alone?", "120/7", "hard", "2(A+B+C)=1/10+1/12+1/15"),
        ("A+B=10 days, B+C=12, C+A=15. Days for A+B+C together?", "120/17", "hard", "half the sum of pairwise"),
        ("A finishes 2/5 of work in 8 days. Remaining work by B in 9 days. Days A+B full job?", "90/7", "medium", "find both rates"),
        ("Machine A produces 100 units/day, B 150. Days for 1000 units both running?", "4", "easy", "250/day"),
        ("A does a job in 16 days. With B, in 10 days. Days B alone?", "80/3", "medium", "1/B=1/10-1/16"),
        ("4 painters finish a wall in 6 days. Days for 3 painters?", "8", "easy", "man-days"),
        ("A works at 50% of B. Together 12 days. Days for B alone?", "18", "medium", "rates k and 2k"),
        ("Pipe fills in 8 h. After 3 h of filling, a leak empties remaining in 10 h. Leak empty-full hours?", "16", "hard", "remaining 5/8 emptied in 10h"),
        ("A,B together 5 days; A works alone for 3 days then B alone finishes rest in 6 days. Days A alone?", "15/2", "hard", "system of rates"),
        ("Two workers A,B: A alone 9 days, B alone 18. Fraction done by A if both work 3 days?", "1/2", "easy", "3/9 + 3/18 wait A only fraction of total? A alone contribution 3/9=1/3 of job — ask carefully"),
        ("If 8 men or 12 women finish in 10 days, days for 4 men and 4 women?", "12", "hard", "equate man=woman rates"),
        ("A can finish in 25 days. After working 10 days, remaining given to B who finishes in 20 days. Days B alone for full?", "100/3", "medium", "B does 3/5 in 20"),
        ("Efficiency of A:B = 3:2. Together 20 days. Days A alone?", "100/3", "medium", "rates 3k,2k"),
        ("A+B finish 60% in 9 days. Rest by A alone in 8 days. Days B alone for full job?", "45", "hard", "find rates from partial"),
        ("Cistern has 2 inlet pipes 20 and 30 min and 1 outlet 15 min. Minutes to fill all open?", "60", "hard", "1/20+1/30-1/15"),
        ("A does half the work in 8 days, B does the other half in 8 days (sequential). Days if both from start?", "8", "easy", "each half → together full in 8"),
        ("10 diggers dig a trench in 12 days. Days for 15 diggers?", "8", "easy", "inverse proportion"),
    ]
    # Fix the awkward q about fraction — replace with cleaner
    rows[32] = (
        "A alone finishes in 9 days, B in 18. They work together for 3 days. What fraction of the job remains?",
        "1/2",
        "easy",
        "work done = 3/9+3/18=1/2",
    )

    qs = []
    tid = "math.aptitude.gen-time-work"
    for i, (problem, answer, diff, hint) in enumerate(rows, start=1):
        qs.append(
            {
                "id": f"{tid}.q{i:04d}",
                "problem": problem,
                "answer": answer,
                "answer_format": "expression",
                "difficulty": diff,
                "solution_steps": [hint],
                "explanation": hint,
                "hint": "Work rate = 1 / time. Combined rates add (or subtract for emptying).",
                "tags": ["time-work", "aptitude", "authored"],
            }
        )
    payload = {
        "schema_version": 1,
        "kind": "math",
        "topic": {
            "topic_id": tid,
            "title": "Time & work (authored)",
            "stage": "foundations",
            "path": ["Aptitude", "Interview", "Time & work"],
            "track": "aptitude",
            "prerequisites": ["math.aptitude.mathqa-physics"],
            "note_topic_ids": ["MT1-T07"],
            "description": "Classic interview time & work / pipes & cisterns with expression answers.",
        },
        "questions": qs,
    }
    out = MATH_Q / "aptitude" / "authored" / "time-work.json"
    _dump(out, payload)
    print(f"wrote {out.relative_to(MATH_Q)} ({len(qs)} q)")


CURRICULUM = {
    "schema_version": 1,
    "name": "Math Daily Path — scratch to graduate",
    "pass_accuracy": 0.8,
    "session_size": 15,
    "levels": [
        {
            "id": "L0",
            "title": "Warm-up",
            "weeks": "1-2",
            "steps": [
                {
                    "order": 1,
                    "note_topic_id": "MT1-T01",
                    "title": "Number systems & divisibility",
                    "prefer_topic_ids": [
                        "math.aptitude.dm-add-sub",
                        "math.aptitude.dm-mul",
                        "math.aptitude.dm-div",
                        "math.aptitude.dm-root",
                        "math.aptitude.gen-prime-factors",
                        "math.aptitude.mathqa-other",
                    ],
                },
                {
                    "order": 2,
                    "note_topic_id": "MT1-T02",
                    "title": "LCM & HCF",
                    "prefer_topic_ids": [
                        "math.aptitude.dm-gcd",
                        "math.aptitude.dm-lcm",
                        "math.aptitude.gen-lcm",
                        "math.aptitude.gen-gcd",
                        "math.aptitude.gen-common-factors",
                    ],
                },
            ],
        },
        {
            "id": "L1",
            "title": "Interview quant core",
            "weeks": "3-5",
            "steps": [
                {
                    "order": 3,
                    "note_topic_id": "MT1-T03",
                    "title": "Percentages",
                    "prefer_topic_ids": ["math.aptitude.mathqa-general", "math.aptitude.gen-percentage"],
                },
                {
                    "order": 4,
                    "note_topic_id": "MT1-T04",
                    "title": "Ratio & proportion",
                    "prefer_topic_ids": ["math.aptitude.sat-algebra"],
                },
                {
                    "order": 5,
                    "note_topic_id": "MT1-T05",
                    "title": "Averages & mixtures",
                    "prefer_topic_ids": ["math.aptitude.sat-data"],
                },
                {
                    "order": 6,
                    "note_topic_id": "MT1-T06",
                    "title": "Time, speed & distance",
                    "prefer_topic_ids": ["math.aptitude.mathqa-physics"],
                },
                {
                    "order": 7,
                    "note_topic_id": "MT1-T07",
                    "title": "Time & work",
                    "prefer_topic_ids": ["math.aptitude.gen-time-work"],
                },
                {
                    "order": 8,
                    "note_topic_id": "MT1-T08",
                    "title": "Profit, loss & discount",
                    "prefer_topic_ids": ["math.aptitude.mathqa-gain", "math.aptitude.gen-profit-loss"],
                },
                {
                    "order": 9,
                    "note_topic_id": "MT1-T09",
                    "title": "Simple & compound interest",
                    "prefer_topic_ids": [
                        "math.aptitude.gen-simple-interest",
                        "math.aptitude.gen-compound-interest",
                    ],
                },
                {
                    "order": 10,
                    "note_topic_id": "MT1-T10",
                    "title": "Permutations & combinations",
                    "prefer_topic_ids": [
                        "math.aptitude.gen-combinations",
                        "math.aptitude.gen-permutations",
                    ],
                },
                {
                    "order": 11,
                    "note_topic_id": "MT1-T11",
                    "title": "Probability",
                    "prefer_topic_ids": [
                        "math.aptitude.mathqa-probability",
                        "math.aptitude.dm-prob",
                        "math.aptitude.gen-dice-prob",
                    ],
                },
                {
                    "order": 12,
                    "note_topic_id": "MT1-T12",
                    "title": "Progressions",
                    "prefer_topic_ids": [
                        "math.aptitude.gen-ap-term",
                        "math.aptitude.gen-ap-sum",
                        "math.aptitude.gen-gp",
                    ],
                },
                {
                    "order": 13,
                    "note_topic_id": "MT1-T14",
                    "title": "Geometry & mensuration",
                    "prefer_topic_ids": [
                        "math.aptitude.sat-geometry",
                        "math.aptitude.mathqa-geometry",
                    ],
                },
                {
                    "order": 14,
                    "note_topic_id": "MT1-T13",
                    "title": "Programming aptitude",
                    "prefer_topic_ids": ["math.aptitude.saket-coding"],
                    "optional": True,
                },
            ],
        },
        {
            "id": "L2",
            "title": "Algebra bridge",
            "weeks": "2-3",
            "steps": [
                {
                    "order": 15,
                    "note_topic_id": "MT2-T01",
                    "title": "Linear & quadratic",
                    "prefer_topic_ids": [
                        "math.aptitude.sat-advanced",
                        "math.aptitude.dm-linear-1d",
                        "math.aptitude.gen-basic-algebra",
                        "math.aptitude.gen-linear-eq",
                        "math.aptitude.gen-quadratic",
                    ],
                },
                {
                    "order": 16,
                    "note_topic_id": "MT2-T02",
                    "title": "Competition algebra",
                    "prefer_topic_ids": [
                        "math.competition.algebra",
                        "math.olympiad.mathnet-algebra",
                    ],
                },
            ],
        },
        {
            "id": "L3",
            "title": "AI/ML math entry",
            "weeks": "ongoing",
            "steps": [
                {
                    "order": 17,
                    "note_topic_id": "MT3-T01",
                    "title": "Vectors for ML",
                    "prefer_topic_ids": ["math.aiml.gen-vector-dot", "math.aiml.gen-vector-cross"],
                },
                {
                    "order": 18,
                    "note_topic_id": "MT4-T01",
                    "title": "Calculus for ML",
                    "prefer_topic_ids": ["math.olympiad.mathnet-calculus"],
                    "notes_first": True,
                },
            ],
        },
        {
            "id": "L4",
            "title": "Olympiad stretch",
            "weeks": "optional",
            "steps": [
                {
                    "order": 19,
                    "note_topic_id": "MT1-T14",
                    "title": "Olympiad geometry",
                    "prefer_topic_ids": ["math.olympiad.mathnet-geometry"],
                    "optional": True,
                },
                {
                    "order": 20,
                    "note_topic_id": "MT1-T01",
                    "title": "Number theory / prealgebra stretch",
                    "prefer_topic_ids": [
                        "math.competition.prealgebra",
                        "math.competition.number-theory",
                        "math.olympiad.mathnet-number",
                    ],
                    "optional": True,
                },
                {
                    "order": 21,
                    "note_topic_id": "MT1-T11",
                    "title": "Competition counting & probability",
                    "prefer_topic_ids": ["math.competition.counting-probability"],
                    "optional": True,
                },
                {
                    "order": 22,
                    "note_topic_id": "MT2-T02",
                    "title": "MathNet mixed",
                    "prefer_topic_ids": ["math.olympiad.mathnet-mixed"],
                    "optional": True,
                },
            ],
        },
    ],
}


def main() -> None:
    retag_geometry()
    move_aiml()
    write_time_work()
    _dump(MATH_Q / "curriculum.json", CURRICULUM)
    print("curriculum rewritten")


if __name__ == "__main__":
    main()
