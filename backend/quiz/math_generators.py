"""Mathgenerator recipe index + on-demand generation into math_questions.

Curated packs stay in data/questions/math/** and are imported separately.
Live generators are the primary path for **core aptitude** improvement:
recipes are MT-tagged; practice can weight weak tags/gen_ids so the user
sees more of what they miss until they learn it.
"""

from __future__ import annotations

import hashlib
import json
import random
import re
import sys
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from backend.math.schemas import MathQuestionIn
from backend.math.services.import_questions import upsert_questions
from backend.paths import ROOT

MG_ROOT = ROOT / "data" / "math" / "imports" / "mathgenerator"

# Name → MT tag (authoritative). Ids are resolved from the live gen_list.
NAME_TO_MT: dict[str, str] = {
    # MT1-T01 numbers
    "addition": "MT1-T01",
    "subtraction": "MT1-T01",
    "multiplication": "MT1-T01",
    "division": "MT1-T01",
    "square_root": "MT1-T01",
    "square": "MT1-T01",
    "cube_root": "MT1-T01",
    "prime_factors": "MT1-T01",
    "factors": "MT1-T01",
    "is_prime": "MT1-T01",
    "is_composite": "MT1-T01",
    "simplify_square_root": "MT1-T01",
    "fraction_to_decimal": "MT1-T01",
    "divide_fractions": "MT1-T01",
    "fraction_multiplication": "MT1-T01",
    "compare_fractions": "MT1-T01",
    "exponentiation": "MT1-T01",
    "power_of_powers": "MT1-T01",
    "absolute_difference": "MT1-T01",
    "factorial": "MT1-T01",
    # MT1-T02 LCM/HCF
    "lcm": "MT1-T02",
    "common_factors": "MT1-T02",
    "greatest_common_divisor": "MT1-T02",
    # MT1-T03 %
    "percentage": "MT1-T03",
    "percentage_difference": "MT1-T03",
    "percentage_error": "MT1-T03",
    # MT1-T08 P&L
    "profit_loss_percent": "MT1-T08",
    # MT1-T09 interest
    "simple_interest": "MT1-T09",
    "compound_interest": "MT1-T09",
    # MT1-T10 P&C
    "combinations": "MT1-T10",
    "permutation": "MT1-T10",
    # MT1-T11 probability / stats lite
    "dice_sum_probability": "MT1-T11",
    "conditional_probability": "MT1-T11",
    "binomial_distribution": "MT1-T11",
    "mean_median": "MT1-T11",
    "data_summary": "MT1-T11",
    "geometric_mean": "MT1-T11",
    "harmonic_mean": "MT1-T11",
    # MT1-T12 progressions
    "arithmetic_progression_term": "MT1-T12",
    "arithmetic_progression_sum": "MT1-T12",
    "geometric_progression": "MT1-T12",
    # MT1-T14 geometry / mensuration
    "area_of_triangle": "MT1-T14",
    "valid_triangle": "MT1-T14",
    "third_angle_of_triangle": "MT1-T14",
    "pythagorean_theorem": "MT1-T14",
    "angle_regular_polygon": "MT1-T14",
    "surface_area_cube": "MT1-T14",
    "surface_area_cuboid": "MT1-T14",
    "surface_area_cylinder": "MT1-T14",
    "volume_cube": "MT1-T14",
    "volume_cuboid": "MT1-T14",
    "volume_cylinder": "MT1-T14",
    "surface_area_cone": "MT1-T14",
    "volume_cone": "MT1-T14",
    "fourth_angle_of_quadrilateral": "MT1-T14",
    "basic_trigonometry": "MT1-T14",
    "sum_of_polygon_angles": "MT1-T14",
    "surface_area_sphere": "MT1-T14",
    "volume_sphere": "MT1-T14",
    "sector_area": "MT1-T14",
    "degree_to_rad": "MT1-T14",
    "radian_to_deg": "MT1-T14",
    "curved_surface_area_cylinder": "MT1-T14",
    "perimeter_of_polygons": "MT1-T14",
    "circumference": "MT1-T14",
    "arc_length": "MT1-T14",
    "area_of_circle": "MT1-T14",
    "volume_cone_frustum": "MT1-T14",
    "equation_of_line_from_two_points": "MT1-T14",
    "area_of_circle_given_center_and_point": "MT1-T14",
    "volume_hemisphere": "MT1-T14",
    "volume_pyramid": "MT1-T14",
    "surface_area_pyramid": "MT1-T14",
    "complementary_and_supplementary_angle": "MT1-T14",
    "area_of_trapezoid": "MT1-T14",
    "angle_btw_vectors": "MT1-T14",
    # MT2 algebra bridge
    "basic_algebra": "MT2-T01",
    "linear_equations": "MT2-T01",
    "quadratic_equation": "MT2-T01",
    "system_of_equations": "MT2-T01",
    "factoring": "MT2-T01",
    "log": "MT2-T01",
    "combine_like_terms": "MT2-T01",
    "expanding": "MT2-T01",
    "complex_quadratic": "MT2-T01",
    "midpoint_of_two_points": "MT2-T01",
    "distance_two_points": "MT2-T01",
    "intersection_of_two_lines": "MT2-T01",
    "line_equation_from_2_points": "MT2-T01",
    # MT3 vectors / LA lite
    "vector_dot": "MT3-T01",
    "vector_cross": "MT3-T01",
    "euclidian_norm": "MT3-T01",
    "matrix_multiplication": "MT3-T01",
    "multiply_int_to_22_matrix": "MT3-T01",
    "int_matrix_22_determinant": "MT3-T01",
    "invert_matrix": "MT3-T01",
    "orthogonal_projection": "MT3-T01",
    # MT4 calculus lite
    "power_rule_differentiation": "MT4-T01",
    "power_rule_integration": "MT4-T01",
    "trig_differentiation": "MT4-T01",
    "definite_integral": "MT4-T01",
    "stationary_points": "MT4-T01",
}

# Core aptitude live-drill pool (interview quant) — generators only for these tags.
APTITUDE_MT_TAGS = frozenset(
    {
        "MT1-T01",
        "MT1-T02",
        "MT1-T03",
        "MT1-T08",
        "MT1-T09",
        "MT1-T10",
        "MT1-T11",
        "MT1-T12",
        "MT1-T14",
        "MT2-T01",
    }
)

SUBJECT_FALLBACK_MT: dict[str, str] = {
    "basic_math": "MT1-T01",
    "misc": "MT1-T01",
    "statistics": "MT1-T11",
    "geometry": "MT1-T14",
    "algebra": "MT2-T01",
    "calculus": "MT4-T01",
    "computer_science": "MT1-T13",
}

_SLUG_RE = re.compile(r"[^a-z0-9]+")


@dataclass(frozen=True)
class GeneratorRecipe:
    gen_id: int
    name: str
    subject: str
    note_topic_id: str
    topic_id: str
    title: str
    aptitude_core: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": "generator",
            "gen_id": self.gen_id,
            "name": self.name,
            "subject": self.subject,
            "note_topic_ids": [self.note_topic_id],
            "topic_id": self.topic_id,
            "title": self.title,
            "stage": "foundations",
            "track": "generator",
            "path": ["Mathgenerator", self.subject, self.name],
            "description": f"On-demand via mathgenerator id={self.gen_id}",
            "question_count": None,
            "source": "mathgenerator",
            "aptitude_core": self.aptitude_core,
        }


def _ensure_mg_path() -> Path:
    if not MG_ROOT.is_dir():
        raise FileNotFoundError(f"mathgenerator clone missing: {MG_ROOT}")
    root = str(MG_ROOT)
    if root not in sys.path:
        sys.path.insert(0, root)
    return MG_ROOT


def _slug(name: str) -> str:
    s = _SLUG_RE.sub("-", (name or "").strip().lower()).strip("-")
    return s or "gen"


def list_recipes(*, refresh: bool = False) -> list[GeneratorRecipe]:
    cache_attr = "_recipes_cache"
    if not refresh and getattr(list_recipes, cache_attr, None) is not None:
        return getattr(list_recipes, cache_attr)
    _ensure_mg_path()
    from mathgenerator._gen_list import gen_list  # type: ignore

    out: list[GeneratorRecipe] = []
    for gen_id, (name, subject) in enumerate(gen_list):
        if not name or str(name).upper() == "DELETED":
            continue
        name_s = str(name)
        subject_s = str(subject or "misc").lower()
        mt = NAME_TO_MT.get(name_s) or SUBJECT_FALLBACK_MT.get(subject_s, "MT1-T01")
        mt = mt.upper()
        slug = _slug(name_s)
        topic_id = f"math.gen.{slug}"
        title = name_s.replace("_", " ").title()
        out.append(
            GeneratorRecipe(
                gen_id=gen_id,
                name=name_s,
                subject=subject_s,
                note_topic_id=mt,
                topic_id=topic_id,
                title=title,
                aptitude_core=mt in APTITUDE_MT_TAGS,
            )
        )
    setattr(list_recipes, cache_attr, out)
    return out


def recipe_by_topic_id(topic_id: str) -> GeneratorRecipe | None:
    want = (topic_id or "").strip().lower()
    for r in list_recipes():
        if r.topic_id == want or f"math.gen.{r.gen_id}" == want:
            return r
    if want.startswith("math.gen.") and want[9:].isdigit():
        gid = int(want[9:])
        for r in list_recipes():
            if r.gen_id == gid:
                return r
    return None


def recipes_for_note_topic(note_topic_id: str) -> list[GeneratorRecipe]:
    tag = (note_topic_id or "").strip().upper()
    return [r for r in list_recipes() if r.note_topic_id == tag]


def aptitude_recipes() -> list[GeneratorRecipe]:
    return [r for r in list_recipes() if r.aptitude_core]


def generate_one(recipe: GeneratorRecipe) -> tuple[str, str] | None:
    _ensure_mg_path()
    import mathgenerator as mg  # type: ignore

    try:
        problem, answer = mg.gen_by_id(recipe.gen_id)
    except Exception:  # noqa: BLE001
        return None
    problem = str(problem or "").strip()
    answer = str(answer or "").strip().strip("$")
    if not problem or not answer or problem.upper() == "DELETED":
        return None
    return problem, answer


def _external_id(recipe: GeneratorRecipe, prompt: str, answer: str) -> str:
    h = hashlib.sha1(f"{recipe.gen_id}|{prompt}|{answer}".encode("utf-8")).hexdigest()[:16]
    return f"mg-{recipe.gen_id}-{h}"


def _weakness_weights(
    db: Session,
    *,
    user_id: int,
    recipes: list[GeneratorRecipe],
) -> list[float]:
    """Higher weight for MT tags / gen_ids the user recently missed."""
    from backend.models.review_card import ReviewCard
    from backend.quiz.review_cards import weak_concepts_for_retrieval

    weak_labels = {w.lower() for w in weak_concepts_for_retrieval(db, user_id, limit=20)}
    gen_misses: dict[int, int] = defaultdict(int)
    mt_misses: dict[str, int] = defaultdict(int)

    rows = (
        db.query(ReviewCard)
        .filter(ReviewCard.user_id == user_id, ReviewCard.domain == "math")
        .order_by(ReviewCard.updated_at.desc())
        .limit(200)
        .all()
    )
    for row in rows:
        try:
            payload = json.loads(row.payload_json or "{}")
        except json.JSONDecodeError:
            payload = {}
        srs = {}
        try:
            srs = json.loads(row.srs_json or "{}")
        except json.JSONDecodeError:
            pass
        # Prefer cards that are still hard / due-ish
        reps = int(srs.get("reps") or srs.get("review_count") or 0)
        stability = float(srs.get("stability") or 0)
        hard = reps < 3 or stability < 5
        if not hard and row.topic and row.topic.lower() not in weak_labels:
            continue
        gid = payload.get("gen_id")
        if gid is not None:
            try:
                gen_misses[int(gid)] += 3 if hard else 1
            except (TypeError, ValueError):
                pass
        for tag in payload.get("note_topic_ids") or []:
            mt_misses[str(tag).upper()] += 2 if hard else 1
        topic = (row.topic or "").upper()
        if topic.startswith("MT"):
            mt_misses[topic] += 1

    weights: list[float] = []
    for r in recipes:
        w = 1.0
        w += float(gen_misses.get(r.gen_id, 0)) * 2.0
        w += float(mt_misses.get(r.note_topic_id, 0)) * 1.5
        if r.note_topic_id.lower() in weak_labels or r.topic_id.lower() in weak_labels:
            w += 4.0
        if any(r.note_topic_id.lower() in lab or r.name.lower() in lab for lab in weak_labels):
            w += 2.0
        weights.append(max(0.25, w))
    return weights


def _pick_weighted(recipes: list[GeneratorRecipe], weights: list[float]) -> GeneratorRecipe:
    total = sum(weights) or len(recipes)
    x = random.random() * total
    acc = 0.0
    for r, w in zip(recipes, weights):
        acc += w
        if x <= acc:
            return r
    return recipes[-1]


def generate_quiz_items(
    db: Session,
    *,
    recipe: GeneratorRecipe | None = None,
    topic_id: str | None = None,
    note_topic_id: str | None = None,
    count: int = 10,
    adaptive: bool = False,
    aptitude_only: bool = False,
    user_id: int | None = None,
    boost_note_topics: list[str] | None = None,
) -> list[dict[str, Any]]:
    """Generate ``count`` items, upsert into math_questions, return quiz-engine items."""
    recipes: list[GeneratorRecipe] = []
    if recipe:
        recipes = [recipe]
    elif topic_id:
        r = recipe_by_topic_id(topic_id)
        if r:
            recipes = [r]
    elif note_topic_id:
        recipes = recipes_for_note_topic(note_topic_id)
        if aptitude_only:
            recipes = [r for r in recipes if r.aptitude_core]
        if not recipes and (aptitude_only or adaptive):
            recipes = aptitude_recipes()
    elif aptitude_only or adaptive:
        recipes = aptitude_recipes()
    if aptitude_only and recipes:
        core = [r for r in recipes if r.aptitude_core]
        if core:
            recipes = core
    if not recipes:
        raise ValueError("No mathgenerator recipe matched that topic.")

    want = max(1, min(int(count or 10), 40))
    weights = [1.0] * len(recipes)
    if adaptive and user_id is not None:
        weights = _weakness_weights(db, user_id=user_id, recipes=recipes)
    if boost_note_topics:
        boost = {t.strip().upper() for t in boost_note_topics if t}
        weights = [
            w * (4.0 if r.note_topic_id in boost else 1.0) for r, w in zip(recipes, weights)
        ]

    items: list[dict[str, Any]] = []
    to_upsert: list[MathQuestionIn] = []
    attempts = 0
    max_attempts = want * 10
    while len(items) < want and attempts < max_attempts:
        attempts += 1
        r = _pick_weighted(recipes, weights) if len(recipes) > 1 else recipes[0]
        pair = generate_one(r)
        if not pair:
            continue
        prompt, answer = pair
        ext = _external_id(r, prompt, answer)
        meta = {
            "gen_id": r.gen_id,
            "note_topic_ids": [r.note_topic_id],
            "topic_id": r.topic_id,
            "generator_name": r.name,
            "adaptive": adaptive,
        }
        to_upsert.append(
            MathQuestionIn(
                topic=r.topic_id,
                prompt=prompt[:1000],
                expected_answer=answer[:500],
                explanation=f"mathgenerator:{r.name}",
                difficulty="easy",
                answer_format="expression",
                tags=["mathgenerator", f"gen-{r.gen_id}", r.note_topic_id],
                external_id=ext,
                source="mathgenerator",
                metadata=meta,
            )
        )
        items.append(
            {
                "kind": "math",
                "id": ext,
                "prompt": prompt,
                "expected_answer": answer,
                "answer_format": "expression",
                "difficulty": "easy",
                "explanation": f"Generated by mathgenerator ({r.name})",
                "hint": r.title,
                "topic": r.topic_id,
                "topic_id": r.topic_id,
                "topic_title": r.title,
                "tags": ["mathgenerator", r.note_topic_id],
                "content_kind": "math",
                "note_topic_ids": [r.note_topic_id],
                "gen_id": r.gen_id,
                "repeat_until_correct": True,
            }
        )

    if to_upsert:
        upsert_questions(db, to_upsert, default_source="mathgenerator")

    if not items:
        raise ValueError("mathgenerator produced no usable questions for this recipe.")
    return items


def catalog_generators() -> dict[str, Any]:
    recipes = list_recipes()
    aptitude = [r for r in recipes if r.aptitude_core]
    return {
        "generators": [r.to_dict() for r in recipes],
        "generator_count": len(recipes),
        "aptitude_generator_count": len(aptitude),
        "by_note_topic": _group_by_mt(recipes),
        "aptitude_by_note_topic": _group_by_mt(aptitude),
    }


def _group_by_mt(recipes: list[GeneratorRecipe]) -> dict[str, int]:
    out: dict[str, int] = {}
    for r in recipes:
        out[r.note_topic_id] = out.get(r.note_topic_id, 0) + 1
    return out
