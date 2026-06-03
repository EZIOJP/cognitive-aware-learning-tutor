from pydantic import BaseModel, Field


class LifeDailyIn(BaseModel):
    sleep_hours: float = 0
    sleep_quality: int = Field(default=3, ge=1, le=5)
    exercise_minutes: int = Field(default=0, ge=0)
    water_glasses: int = Field(default=0, ge=0)
    meals_healthy: int = Field(default=0, ge=0, le=3)
    study_minutes: int = Field(default=0, ge=0)
    tasks_completed: int = Field(default=0, ge=0)
    deep_work_blocks: int = Field(default=0, ge=0)
    screen_time_hours: float = Field(default=0, ge=0)
    social_media_minutes: int = Field(default=0, ge=0)
    outdoor_minutes: int = Field(default=0, ge=0)
    mood_score: int = Field(default=3, ge=1, le=5)
    stress_level: int = Field(default=3, ge=1, le=5)
    meditation_minutes: int = Field(default=0, ge=0)
