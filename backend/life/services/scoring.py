"""Life score 0–100 from daily log fields (mirrors GoalTracker weights)."""


def compute_life_score(
    *,
    sleep_hours: float,
    sleep_quality: int,
    exercise_minutes: int,
    water_glasses: int,
    meals_healthy: int,
    study_minutes: int,
    tasks_completed: int,
    deep_work_blocks: int,
    screen_time_hours: float,
    social_media_minutes: int,
    outdoor_minutes: int,
    mood_score: int,
    stress_level: int,
    meditation_minutes: int,
) -> int:
    health = min(
        100,
        int(sleep_hours / 8 * 35)
        + sleep_quality * 8
        + min(exercise_minutes, 60) / 60 * 25
        + min(water_glasses, 8) / 8 * 15
        + meals_healthy * 5,
    )
    productivity = min(
        100,
        min(study_minutes, 240) / 240 * 50
        + min(tasks_completed, 10) * 5
        + deep_work_blocks * 8,
    )
    digital = max(0, 100 - int(screen_time_hours * 8) - int(social_media_minutes / 10) + min(outdoor_minutes, 60))
    mental = min(100, mood_score * 15 + max(0, 6 - stress_level) * 8 + min(meditation_minutes, 30) * 2)
    return max(0, min(100, int(health * 0.3 + productivity * 0.3 + digital * 0.2 + mental * 0.2)))
