from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict

from backend.paths import DB_PATH, ROOT


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

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
    eeg_enabled: bool = False
    eeg_udp_port: int = 5005
    ollama_enabled: bool = False
    llm_provider: str = "lmstudio"
    ollama_url: str = "http://127.0.0.1:1234"
    ollama_model: str = "google/gemma-4-e4b"
    llm_max_tokens: int = 8192
    corpus_grounded_notes: bool = False
    llm_api_key: str = "lm-studio"
    llm_default_tier: str = "medium"
    llm_route_profile: str = "hybrid"
    llm_tier_light: str = ""
    llm_tier_medium: str = ""
    llm_tier_heavy: str = ""
    llm_cloud_api_key: str = ""
    llm_anthropic_api_key: str = ""
    llm_openrouter_api_key: str = ""
    llm_openrouter_site_url: str = ""
    llm_openrouter_app_name: str = "CALT"
    llm_heavy_daily_soft_cap: int = 50
    llm_context_char_limit: int = 120_000
    nim_api_key: str = ""
    nim_model: str = "google/gemma-4-31b-it"
    nim_vision_model: str = "nvidia/nemotron-nano-vl-8b-v1"
    nim_base_url: str = "https://integrate.api.nvidia.com/v1"


@lru_cache
def get_settings() -> Settings:
    return Settings()
