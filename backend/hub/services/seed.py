import json

from sqlalchemy.orm import Session

from backend.models import ReadingDefinition, UserPlugin

DEFAULT_DEFINITIONS = [
    ("sleep_hours", "Sleep", "hours", "manual", "life"),
    ("study_minutes", "Study time", "minutes", "manual", "life"),
    ("productive_score", "Productive score", "score", "batch", "hub"),
    ("vocab_quiz_complete", "Vocab quiz", "count", "batch", "vocab"),
    ("global_quiz_complete", "Global quiz", "count", "batch", "hub"),
    ("math_attempt", "Math attempt", "count", "batch", "math"),
    ("face_attention", "Face attention", "score", "realtime", "math"),
    ("eeg_attention", "EEG attention", "score", "realtime", "math"),
    ("browser_event", "Browser activity", "count", "realtime", "browser"),
    ("calories", "Calories", "kcal", "manual", "nutrition"),
    ("steps", "Steps", "count", "batch", "health"),
]

from backend.hub.services.catalog import default_plugin_toggles

DEFAULT_PLUGINS = default_plugin_toggles()


def seed_reading_definitions(db: Session) -> None:
    for slug, label, unit, source_type, feature_id in DEFAULT_DEFINITIONS:
        if db.query(ReadingDefinition).filter(ReadingDefinition.slug == slug).first():
            continue
        db.add(
            ReadingDefinition(
                slug=slug,
                label=label,
                unit=unit,
                source_type=source_type,
                feature_id=feature_id,
                is_system=True,
            )
        )
    db.commit()


def seed_user_plugins(db: Session, user_id: int) -> None:
    for plugin_id, enabled in DEFAULT_PLUGINS:
        row = (
            db.query(UserPlugin)
            .filter(UserPlugin.user_id == user_id, UserPlugin.plugin_id == plugin_id)
            .first()
        )
        if row:
            continue
        db.add(
            UserPlugin(
                user_id=user_id,
                plugin_id=plugin_id,
                enabled=enabled,
                config_json="{}",
            )
        )
    db.commit()
