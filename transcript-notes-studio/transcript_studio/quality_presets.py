"""Map UI quality preset to generate/parse settings."""

from __future__ import annotations

from typing import Any

PRESETS: dict[str, dict[str, Any]] = {
    "fast": {
        "fast_mode": True,
        "max_llm_chunks": 12,
        "legacy_notes_pipeline": True,
        "use_semantic_chunking": False,
        "refine_second_pass": False,
        "llm_pause_sec": 0.0,
        "parse_speed": 50,
    },
    "balanced": {
        "fast_mode": False,
        "max_llm_chunks": 20,
        "legacy_notes_pipeline": False,
        "use_semantic_chunking": True,
        "refine_second_pass": False,
        "llm_pause_sec": 1.0,
        "parse_speed": 65,
    },
    "quality": {
        "fast_mode": False,
        "max_llm_chunks": 28,
        "legacy_notes_pipeline": False,
        "use_semantic_chunking": False,
        "refine_second_pass": False,
        "llm_pause_sec": 3.0,
        "parse_speed": 80,
    },
}


def apply_quality_preset(name: str) -> dict[str, Any]:
    key = name.strip().lower()
    if key not in PRESETS:
        key = "balanced"
    return dict(PRESETS[key])
