"""Stuckness scoring + LaTeX-aware Socratic intervention."""

from __future__ import annotations

import re
from dataclasses import dataclass

from backend.math.ocr_service import OcrResult, recognize_canvas
from backend.math.ollama_tutor import generate_tutor_hint
from backend.math.rule_tutor import rule_based_hint

STUCKNESS_THRESHOLD = 0.50

_ANSWER_PATTERNS = (
    r"x\s*=\s*[-+]?\d",
    r"=\s*[-+]?\d+\.?\d*\s*$",
    r"the answer is",
    r"solution:\s*",
)


@dataclass
class InterventionResult:
    session_snapshot_id: str
    latex: str
    incomplete_step: bool
    confidence: float
    stuckness: float
    triggered: bool
    hint: str
    question: str
    detected_concept: str
    use_llm: bool
    teacher_latex: str = ""
    needs_review: bool = False


def compute_stuckness(
    *,
    gamma: float = 55.0,
    attention: float = 0.0,
    canvas_idle_seconds: float = 0.0,
    eraser_events: int = 0,
    idle_seconds: float | None = None,
    eraser_strokes: int | None = None,
    ocr: OcrResult | None = None,
) -> float:
    """Score 0–1 (ironclad v1 formula) — intervention fires when >= STUCKNESS_THRESHOLD."""
    idle = canvas_idle_seconds if canvas_idle_seconds else (idle_seconds or 0.0)
    erasers = eraser_events if eraser_events else (eraser_strokes or 0)
    score = (
        0.4 * min(idle / 90, 1.0)
        + 0.3 * min(erasers / 5, 1.0)
        + 0.3 * min(max((gamma - 55) / 30, 0), 1.0)
    )
    # OCR signals nudge borderline cases (optional, small)
    if ocr is not None and score >= 0.35:
        if ocr.incomplete_step:
            score += 0.05
        if not ocr.latex:
            score += 0.05
    return min(1.0, score)


def _hint_passes_socratic_check(hint: str, question: str) -> bool:
    blob = f"{hint} {question}".lower()
    return not any(re.search(p, blob, re.I) for p in _ANSWER_PATTERNS)


def _latex_aware_rule_hint(
    *,
    prompt: str,
    topic: str,
    latex: str,
    incomplete: bool,
    gamma: float,
    attention: float,
) -> dict[str, str]:
    base = rule_based_hint(prompt=prompt, topic=topic, gamma=gamma, attention=attention)
    if latex:
        short = latex[:80] + ("…" if len(latex) > 80 else "")
        if incomplete:
            base["hint"] = (
                f"Your board shows an incomplete step ({short}). "
                "Finish the current transformation before jumping ahead."
            )
            base["question"] = "What single symbol or term is missing to balance this line?"
        else:
            base["hint"] = (
                f"I read `{short}` on your board. Check whether both sides stay equivalent after your last move."
            )
            base["question"] = "Does your next operation preserve equality on both sides?"
        base["detected_concept"] = topic or base["detected_concept"]
    return base


def build_intervention(
    *,
    canvas_image: str,
    paths_json: str | None = None,
    prompt: str = "",
    topic: str = "",
    gamma: float = 0.0,
    attention: float = 0.0,
    canvas_idle_seconds: float = 0.0,
    eraser_events: int = 0,
    idle_seconds: float = 0.0,
    eraser_strokes: int = 0,
    snapshot_id: str,
    ollama_vision_fallback: bool = True,
) -> InterventionResult:
    ocr: OcrResult | None = None
    latex = ""
    incomplete = True
    confidence = 0.0
    teacher_latex = ""
    needs_review = False

    idle = canvas_idle_seconds or idle_seconds
    erasers = eraser_events or eraser_strokes

    if canvas_image and len(canvas_image) > 80:
        try:
            ocr = recognize_canvas(
                canvas_image,
                paths_json=paths_json,
                ollama_vision_fallback=ollama_vision_fallback,
            )
            latex = ocr.latex
            incomplete = ocr.incomplete_step
            confidence = ocr.confidence
            teacher_latex = getattr(ocr, "teacher_latex", "") or ""
            needs_review = getattr(ocr, "needs_review", False)
        except (ImportError, ValueError, RuntimeError):
            ocr = None

    stuckness = compute_stuckness(
        gamma=gamma,
        attention=attention,
        canvas_idle_seconds=idle,
        eraser_events=erasers,
        ocr=ocr,
    )
    triggered = stuckness >= STUCKNESS_THRESHOLD

    concept = topic or "whiteboard work"
    enriched_prompt = prompt
    if latex:
        enriched_prompt = (
            f"{prompt}\nStudent is working on: {latex}. "
            f"Step appears incomplete: {incomplete}."
        ).strip()

    ruled = _latex_aware_rule_hint(
        prompt=enriched_prompt,
        topic=concept,
        latex=latex,
        incomplete=incomplete,
        gamma=gamma,
        attention=attention,
    )

    hint = ruled["hint"]
    question = ruled["question"]
    detected = ruled["detected_concept"]
    use_llm = False

    if triggered:
        llm = generate_tutor_hint(
            prompt=f"{enriched_prompt}\nRecognized LaTeX: {latex or '(none)'}",
            topic=detected,
            gamma=gamma,
            attention=attention,
            canvas_image=canvas_image,
        )
        if llm and _hint_passes_socratic_check(llm["hint"], llm["question"]):
            hint = llm["hint"]
            question = llm["question"]
            detected = llm.get("detected_concept", detected)
            use_llm = True

    if not triggered:
        hint = "Keep writing — no strong stuck signal yet. Add one more step to your board."
        question = "What are you trying to isolate or simplify?"

    return InterventionResult(
        session_snapshot_id=snapshot_id,
        latex=latex,
        incomplete_step=incomplete,
        confidence=confidence,
        stuckness=stuckness,
        triggered=triggered,
        hint=hint,
        question=question,
        detected_concept=detected,
        use_llm=use_llm,
        teacher_latex=teacher_latex,
        needs_review=needs_review,
    )
