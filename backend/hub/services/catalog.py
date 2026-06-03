"""System feature catalog — maps backend plugin ids to UI modules and default metrics."""

from __future__ import annotations

SYSTEM_FEATURE_CATALOG: list[dict] = [
    {
        "plugin_id": "core",
        "name": "Core Hub",
        "description": "Dashboard, settings, central readings database, export.",
        "kind": "coded",
        "is_core": True,
        "default_enabled": True,
        "frontend_ids": ["core"],
        "metrics": [],
    },
    {
        "plugin_id": "math-tutor",
        "name": "Math Tutor",
        "description": "Practice, whiteboard, reports; optional EEG + focus mirror.",
        "kind": "coded",
        "is_core": False,
        "default_enabled": True,
        "frontend_ids": ["math-tutor"],
        "metrics": [{"slug": "math_attempt", "label": "Math attempt", "unit": "count", "source_type": "batch"}],
    },
    {
        "plugin_id": "gre-vocab",
        "name": "GRE Vocabulary",
        "description": "Word groups, adaptive quiz, and study cycle.",
        "kind": "coded",
        "is_core": False,
        "default_enabled": True,
        "frontend_ids": ["gre-vocab"],
        "metrics": [{"slug": "vocab_quiz_complete", "label": "Vocab quiz", "unit": "count", "source_type": "batch"}],
    },
    {
        "plugin_id": "life-tracker",
        "name": "Life & Behavior Tracker",
        "description": "Daily wellbeing, life score, browser extension stats.",
        "kind": "coded",
        "is_core": False,
        "default_enabled": True,
        "frontend_ids": ["life-tracker"],
        "metrics": [
            {"slug": "sleep_hours", "label": "Sleep", "unit": "hours", "source_type": "manual"},
            {"slug": "study_minutes", "label": "Study time", "unit": "minutes", "source_type": "manual"},
            {"slug": "browser_event", "label": "Browser activity", "unit": "count", "source_type": "realtime"},
            {"slug": "productive_score", "label": "Productive score", "unit": "score", "source_type": "batch"},
        ],
    },
    {
        "plugin_id": "eeg",
        "name": "EEG / Brain Activity",
        "description": "ESP32 UDP stream (or dev simulation) → eeg_attention in hub.",
        "kind": "coded",
        "is_core": False,
        "default_enabled": False,
        "frontend_ids": ["eeg"],
        "metrics": [{"slug": "eeg_attention", "label": "EEG attention", "unit": "score", "source_type": "realtime"}],
    },
    {
        "plugin_id": "focus-mirror",
        "name": "Focus Mirror",
        "description": "Python face_tracker.py → face_attention (mirrored OpenCV window).",
        "kind": "coded",
        "is_core": False,
        "default_enabled": False,
        "frontend_ids": ["focus-mirror"],
        "metrics": [{"slug": "face_attention", "label": "Face attention", "unit": "score", "source_type": "realtime"}],
    },
    {
        "plugin_id": "nutrinode",
        "name": "NutriNode",
        "description": "Nutrition logging and optional live hardware feed.",
        "kind": "coded",
        "is_core": False,
        "default_enabled": False,
        "frontend_ids": ["nutrinode"],
        "metrics": [{"slug": "calories", "label": "Calories", "unit": "kcal", "source_type": "manual"}],
    },
]

BACKEND_TO_FRONTEND_PLUGIN: dict[str, list[str]] = {}
for entry in SYSTEM_FEATURE_CATALOG:
    BACKEND_TO_FRONTEND_PLUGIN[entry["plugin_id"]] = entry.get("frontend_ids", [entry["plugin_id"]])


def catalog_for_ui() -> list[dict]:
    return [e for e in SYSTEM_FEATURE_CATALOG if not e.get("hidden_in_ui")]


def default_plugin_toggles() -> list[tuple[str, bool]]:
    return [(e["plugin_id"], e["default_enabled"]) for e in SYSTEM_FEATURE_CATALOG]
