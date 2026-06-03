from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict

from backend.paths import DB_PATH


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str = f"sqlite:///{DB_PATH.as_posix()}"
    jwt_secret: str = "change-this-in-production"
    jwt_algo: str = "HS256"
    jwt_expire_minutes: int = 60 * 24 * 7
    dev_mode: bool = True
    app_env: str = "development"
    expose_password_plain: bool = True
    cors_origins: str = "*"
    group_size: int = 30
    mastery_mastered: int = 6
    words_source: str = "auto"
    seed_words_on_startup: bool = True


@lru_cache
def get_settings() -> Settings:
    return Settings()
