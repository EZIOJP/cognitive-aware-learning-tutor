from pydantic import BaseModel, Field


class LifeDailyIn(BaseModel):
    """Partial daily log — only provided fields are applied (merge patch)."""

    sleep_hours: float | None = None
    sleep_quality: int | None = Field(default=None, ge=1, le=5)
    exercise_minutes: int | None = Field(default=None, ge=0)
    water_glasses: int | None = Field(default=None, ge=0)
    meals_healthy: int | None = Field(default=None, ge=0, le=3)
    study_minutes: int | None = Field(default=None, ge=0)
    tasks_completed: int | None = Field(default=None, ge=0)
    deep_work_blocks: int | None = Field(default=None, ge=0)
    screen_time_hours: float | None = Field(default=None, ge=0)
    social_media_minutes: int | None = Field(default=None, ge=0)
    outdoor_minutes: int | None = Field(default=None, ge=0)
    mood_score: int | None = Field(default=None, ge=1, le=5)
    stress_level: int | None = Field(default=None, ge=1, le=5)
    meditation_minutes: int | None = Field(default=None, ge=0)


# Fields that must come from wearables / internal services — not the Life Tracker form.
WEARABLE_OWNED_FIELDS = frozenset(
    {
        "sleep_hours",
        "sleep_quality",
        "exercise_minutes",
    }
)

# Manual Life Tracker form is disabled; only these may be patched by clients (e.g. Pomodoro).
CLIENT_ALLOWED_FIELDS = frozenset(
    {
        "study_minutes",
    }
)
