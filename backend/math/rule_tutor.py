"""Rule-based math tutor hints — no GPU or network required."""

from __future__ import annotations


def rule_based_hint(
    *,
    prompt: str,
    topic: str,
    gamma: float,
    attention: float,
) -> dict[str, str]:
    concept = (topic or "this problem").strip()
    topic_key = concept.lower()
    stress = gamma > 55 or (0 < attention < 45)
    p = (prompt or "").strip()

    if stress:
        hint = (
            "Your attention signal looks strained — pause, breathe, and write only the next single step. "
            "Do not rush to the final answer."
        )
        question = "What is the very next line you can add to the board without guessing?"
    elif "linear" in topic_key or "equation" in p.lower():
        hint = "Isolate the unknown on one side: simplify both sides, then undo operations in reverse order (÷ before −)."
        question = "After simplifying, what operation removes the constant term?"
    elif "quadratic" in topic_key or "x^2" in p or "x²" in p:
        hint = "Check if factoring works; otherwise use the quadratic formula and label a, b, c from standard form."
        question = "Is this factorable, or do you need the formula?"
    elif "derivative" in topic_key or "d/dx" in p.lower():
        hint = "Identify the outer and inner functions; apply the chain rule step by step before combining terms."
        question = "Which rule applies first: power, product, quotient, or chain?"
    elif "integral" in topic_key or "∫" in p:
        hint = "Look for substitution (u-sub) or a standard antiderivative pattern before integrating by parts."
        question = "What substitution makes the integrand simpler?"
    elif "probability" in topic_key or "prob" in p.lower():
        hint = "List the sample space, count favorable outcomes, and check whether events are independent."
        question = "Are you using combinations, permutations, or simple equally likely outcomes?"
    elif p:
        short = p[:100] + ("…" if len(p) > 100 else "")
        hint = f'For “{short}”, name givens and the target quantity before any arithmetic.'
        question = "What are you solving for, and what units should the answer have?"
    else:
        hint = "Sketch the problem on the whiteboard; label givens, unknowns, and one intermediate step."
        question = "What did you try first, and where did it stop making sense?"

    return {
        "hint": hint,
        "question": question,
        "detected_concept": concept,
    }
