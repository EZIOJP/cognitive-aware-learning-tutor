"""Sync live OCR-related source files into docs/exports/math-ocr/."""

from __future__ import annotations

import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EXPORT = ROOT / "docs" / "exports" / "math-ocr"


def _copy_tree(src_dir: Path, dst_dir: Path, *, suffixes: set[str] | None = None) -> int:
    n = 0
    if not src_dir.is_dir():
        return 0
    for src in sorted(src_dir.rglob("*")):
        if not src.is_file():
            continue
        if suffixes and src.suffix not in suffixes:
            continue
        if "__pycache__" in src.parts:
            continue
        rel = src.relative_to(src_dir)
        dst = dst_dir / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        n += 1
    return n


def _copy_file(src_rel: str, dst_rel: str) -> bool:
    src = ROOT / src_rel
    dst = EXPORT / dst_rel
    if not src.is_file():
        print(f"  missing: {src_rel}")
        return False
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
    return True


def main() -> None:
    total = 0

    # Backend math module (full tree)
    total += _copy_tree(ROOT / "backend" / "math", EXPORT / "backend" / "math", suffixes={".py", ".json"})

    # Frontend canvas + math pages
    total += _copy_tree(
        ROOT / "src" / "components" / "math-canvas",
        EXPORT / "frontend" / "src" / "components" / "math-canvas",
    )
    total += _copy_tree(
        ROOT / "src" / "pages" / "math",
        EXPORT / "frontend" / "src" / "pages" / "math",
    )

    singles = [
        ("src/api/mathClient.ts", "frontend/src/api/mathClient.ts"),
        ("src/features/quiz/MathQuizAnswerPanel.tsx", "frontend/src/features/quiz/MathQuizAnswerPanel.tsx"),
        ("src/features/quiz/GlobalQuizRunner.tsx", "frontend/src/features/quiz/GlobalQuizRunner.tsx"),
        ("src/study-room/hooks/useStudyRoomOcr.ts", "frontend/src/study-room/hooks/useStudyRoomOcr.ts"),
        ("src/context/StudySessionContext.tsx", "frontend/src/context/StudySessionContext.tsx"),
        ("src/app/components/AITutorIntervention.tsx", "frontend/src/app/components/AITutorIntervention.tsx"),
        ("src/app/components/MathSplitWhiteboard.tsx", "frontend/src/app/components/MathSplitWhiteboard.tsx"),
        ("src/app/components/MathWhiteboard.tsx", "frontend/src/app/components/MathWhiteboard.tsx"),
        ("src/plugins/math_tutor_plugin.tsx", "frontend/src/plugins/math_tutor_plugin.tsx"),
        ("src/pages/study/StudyRoomPage.tsx", "frontend/src/pages/study/StudyRoomPage.tsx"),
        ("src/styles/education-canvas.css", "frontend/src/styles/education-canvas.css"),
        ("src/components/widgets/SymPyCalculatorWidget.tsx", "frontend/src/components/widgets/SymPyCalculatorWidget.tsx"),
        ("backend/requirements-ocr.txt", "backend/requirements-ocr.txt"),
        ("backend/main.py", "backend/main.py"),
        ("backend/quiz/handler.py", "backend/quiz/handler.py"),
        ("backend/models/math.py", "backend/models/math.py"),
        ("backend/models/math_question.py", "backend/models/math_question.py"),
        ("backend/integrations/nim_client.py", "backend/integrations/nim_client.py"),
        ("backend/vocab/routes.py", "backend/vocab/routes.py"),
        ("scripts/install_ocr.bat", "scripts/install_ocr.bat"),
        ("scripts/install_ocr.sh", "scripts/install_ocr.sh"),
        ("scripts/install_unimernet.bat", "scripts/install_unimernet.bat"),
        ("scripts/install_unimernet.py", "scripts/install_unimernet.py"),
        ("scripts/convert_unimernet_onnx.py", "scripts/convert_unimernet_onnx.py"),
        ("scripts/eval_ocr_cdm.py", "scripts/eval_ocr_cdm.py"),
        ("scripts/sync_math_ocr_export.py", "scripts/sync_math_ocr_export.py"),
        ("scripts/retrain_texteller.py", "scripts/retrain_texteller.py"),
        ("scripts/retrain_texteller.bat", "scripts/retrain_texteller.bat"),
        ("scripts/retrain_stroke_symbol.py", "scripts/retrain_stroke_symbol.py"),
        ("scripts/retrain_stroke_symbol.bat", "scripts/retrain_stroke_symbol.bat"),
        ("scripts/recalibrate_structure.py", "scripts/recalibrate_structure.py"),
        ("scripts/recalibrate_structure.bat", "scripts/recalibrate_structure.bat"),
        ("scripts/download_texteller.bat", "scripts/download_texteller.bat"),
        ("scripts/download_texteller.sh", "scripts/download_texteller.sh"),
        ("tests/test_math_ocr.py", "tests/test_math_ocr.py"),
        ("tests/test_math_ocr_phases.py", "tests/test_math_ocr_phases.py"),
        ("tests/test_stroke_metrics.py", "tests/test_stroke_metrics.py"),
        ("tests/test_line_detect_structure.py", "tests/test_line_detect_structure.py"),
        ("tests/test_intervention_handler.py", "tests/test_intervention_handler.py"),
        ("tests/test_tutor_silence.py", "tests/test_tutor_silence.py"),
        ("tests/test_training_log.py", "tests/test_training_log.py"),
    ]
    for src_rel, dst_rel in singles:
        if _copy_file(src_rel, dst_rel):
            total += 1

    print(f"Synced {total} files -> {EXPORT}")


if __name__ == "__main__":
    main()
