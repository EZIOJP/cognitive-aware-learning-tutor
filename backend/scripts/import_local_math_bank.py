"""One-time helper: load FE local question sets into math_questions bank."""

from backend.db.base import SessionLocal
from backend.math.schemas import MathQuestionIn
from backend.math.services.import_questions import upsert_questions

# Mirrors src/features/math/data/topics.ts LOCAL_QUESTION_SETS
LOCAL = {
    "Geometry": [
        ("Two supplementary angles. One is 65°. Find the other.", "115", "180° − 65° = 115°."),
        ("Triangle angles 45° and 60°. Third angle?", "75", "180° − 45° − 60° = 75°."),
        ("Diameter 10cm. Radius?", "5", "r = d/2."),
        ("Square side 7cm. Perimeter?", "28", "4 × 7 = 28cm."),
        ("Complement of 35°?", "55", "90° − 35° = 55°."),
    ],
    "Calculus": [
        ("dy/dx: y = x²", "2x", "Power rule."),
        ("dy/dx: y = 3x³ + 2x", "9x^2+2", "Apply power rule per term."),
        ("dy/dx: y = 5x⁴", "20x^3", "4·5x³."),
        ("dy/dx: y = x² + 3x + 1", "2x+3", "2x + 3 + 0."),
        ("dy/dx: y = 2x³ − x²", "6x^2-2x", "6x² − 2x."),
    ],
    "Trigonometry": [
        ("sin(30°) = ?", "0.5", "Standard value 1/2."),
        ("cos(0°) = ?", "1", "Adjacent equals hypotenuse."),
        ("tan(45°) = ?", "1", "Opposite = adjacent."),
        ("sin(90°) = ?", "1", "Maximum sine."),
        ("sin(θ)=0.5, θ in [0,90]", "30", "sin⁻¹(0.5)=30°."),
    ],
    "Algebra": [
        ("Simplify: 3x + 7x + 3", "10x+3", "Combine like terms."),
        ("Simplify: 5(2x + 3)", "10x+15", "Distribute."),
        ("Solve: 2x + 5 = 13", "4", "x = 4."),
        ("Simplify: x² + 3x² − 2x", "4x^2-2x", "4x² − 2x."),
        ("Factor: x² + 5x + 6", "(x+2)(x+3)", "2 and 3."),
    ],
}


def main() -> None:
    items: list[MathQuestionIn] = []
    for topic, rows in LOCAL.items():
        for i, (prompt, answer, explanation) in enumerate(rows, start=1):
            items.append(
                MathQuestionIn(
                    topic=topic,
                    prompt=prompt,
                    expected_answer=answer,
                    explanation=explanation,
                    external_id=f"{topic.lower()}-{i:03d}",
                    source="local_seed",
                )
            )
    db = SessionLocal()
    try:
        result = upsert_questions(db, items, default_source="local_seed")
        print(result.model_dump())
    finally:
        db.close()


if __name__ == "__main__":
    main()
