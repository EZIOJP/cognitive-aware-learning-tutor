from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
CURRICULUM_PATH = ROOT / "data" / "questions" / "math" / "curriculum.json"
QUESTIONS_MATH = ROOT / "data" / "questions" / "math"
NOTES_MATH = ROOT / "data" / "notes" / "math"
META_DIR = QUESTIONS_MATH / "_meta"

SOURCES = frozenset(
    {
        "sat",
        "mathqa",
        "hendrycks",
        "saket",
        "mathgenerator",
        "deepmind",
        "mathnet",
        "authored",
    }
)
EN_HEURISTIC_MIN_CHARS = 24
MODULE_NOTE_FILES = {
    "MT1": "MT1_aptitude_interview_notes.md",
    "MT2": "MT2_algebra_notes.md",
    "MT3": "MT3_linear_algebra_ml_notes.md",
    "MT4": "MT4_calculus_ml_notes.md",
}
