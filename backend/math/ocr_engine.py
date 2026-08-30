"""Dual OCR engine selection: TexTeller + optional UniMERNet-T (Phases 1–2)."""

from __future__ import annotations

import os
from dataclasses import dataclass

from PIL import Image

from backend.math.ocr_service import _ocr_looks_hallucinated, prepare_for_texteller
from backend.math.sympy_repair import apply_repair_pipeline

PRIMARY_ENGINE = os.getenv("OCR_PRIMARY_ENGINE", "auto").strip().lower()


@dataclass
class EngineResult:
    latex: str
    confidence: float
    source: str
    repaired: bool = False
    repair_reason: str = ""


def _conf_for_latex(latex: str, *, base: float) -> float:
    if not latex:
        return 0.0
    from backend.math.ocr_service import latex_is_complete

    return base if latex_is_complete(latex) else max(0.4, base * 0.55)


def recognize_crop(crop: Image.Image) -> EngineResult:
    """
    Run TexTeller and/or UniMERNet, ensemble when both agree, SymPy repair on failure.
    """
    from backend.math.texteller_onnx import recognize_image as texteller_recognize
    from backend.math.texteller_onnx import texteller_available
    from backend.math.unimernet_onnx import recognize_image as unimernet_recognize
    from backend.math.unimernet_onnx import unimernet_available

    tex_avail = texteller_available()
    uni_avail = unimernet_available()
    if not tex_avail and not uni_avail:
        return EngineResult(latex="", confidence=0.0, source="none")

    prepared = prepare_for_texteller(crop)
    tex_latex, uni_latex = "", ""
    tex_conf, uni_conf = 0.0, 0.0

    if tex_avail:
        try:
            tex_latex = texteller_recognize(prepared).strip()
            if tex_latex and _ocr_looks_hallucinated(tex_latex):
                tex_latex = ""
            tex_conf = _conf_for_latex(tex_latex, base=0.85)
        except Exception:
            tex_latex = ""

    if uni_avail:
        try:
            uni_latex = unimernet_recognize(crop).strip()
            if uni_latex and _ocr_looks_hallucinated(uni_latex):
                uni_latex = ""
            uni_conf = _conf_for_latex(uni_latex, base=0.88)
        except Exception:
            uni_latex = ""

    primary = PRIMARY_ENGINE
    if primary not in ("texteller", "unimernet"):
        primary = "unimernet" if uni_avail and not tex_avail else "texteller"

    if primary == "unimernet" and uni_latex:
        main_latex, main_conf, main_src = uni_latex, uni_conf, "unimernet"
        alt_latex, alt_conf, alt_src = tex_latex, tex_conf, "texteller"
    elif tex_latex:
        main_latex, main_conf, main_src = tex_latex, tex_conf, "texteller"
        alt_latex, alt_conf, alt_src = uni_latex, uni_conf, "unimernet"
    elif uni_latex:
        main_latex, main_conf, main_src = uni_latex, uni_conf, "unimernet"
        alt_latex, alt_conf, alt_src = "", 0.0, ""
    else:
        return EngineResult(latex="", confidence=0.0, source="none")

    if (
        tex_latex
        and uni_latex
        and tex_latex.replace(" ", "") == uni_latex.replace(" ", "")
    ):
        main_latex = tex_latex
        main_conf = min(1.0, max(tex_conf, uni_conf) + 0.12)
        main_src = "ensemble_agree"
        alt_latex, alt_conf, alt_src = "", 0.0, ""

    repair = apply_repair_pipeline(
        main_latex,
        main_conf,
        main_src,
        alternate_latex=alt_latex or None,
        alternate_confidence=alt_conf,
        alternate_source=alt_src,
    )
    return EngineResult(
        latex=repair.latex,
        confidence=repair.confidence,
        source=repair.source,
        repaired=repair.repaired,
        repair_reason=repair.repair_reason,
    )
