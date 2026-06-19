"""Local settings — JSON file beside the app + optional .env overrides."""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = PROJECT_ROOT / "config.json"
ENV_PATH = PROJECT_ROOT / ".env"


@dataclass
class AppConfig:
    llm_enabled: bool = True
    llm_provider: str = "lmstudio"
    llm_base_url: str = "http://127.0.0.1:1234"
    llm_model: str = "google/gemma-4-e4b"
    llm_max_tokens: int = 8192
    llm_api_key: str = ""
    transcripts_dir: str = ""
    notes_dir: str = ""
    aggressive_dedup_default: bool = False
    last_transcript: str = ""
    last_output_dir: str = ""
    whisper_engine: str = "transformers"
    whisper_model: str = "openai/whisper-large-v3-turbo"
    whisper_device: str = "auto"
    whisper_language: str = ""
    whisper_task: str = "transcribe"
    last_audio_file: str = ""
    capture_enabled: bool = False
    capture_auto_interval_sec: float = 120.0
    context_folder: str = ""
    refine_second_pass: bool = True
    enrich_with_references: bool = True
    fast_mode: bool = False
    llm_temperature: float = 0.3
    last_session: str = ""
    sessions_dir: str = ""
    captions_method: str = "uia"
    captions_poll_interval: float = 0.5
    captions_duration_sec: float = 0.0
    whisper_live_chunk_sec: float = 10.0
    whisper_live_source: str = "system"
    use_semantic_chunking: bool = True
    semantic_chunk_threshold: float = 0.45
    use_tag_extraction: bool = True
    inject_wikilinks: bool = True
    semantic_cache_enabled: bool = True
    semantic_cache_threshold: float = 0.95
    semantic_cache_max_age_days: int = 30

    def transcripts_path(self) -> Path:
        if self.transcripts_dir.strip():
            return Path(self.transcripts_dir).expanduser()
        return PROJECT_ROOT / "data" / "transcripts"

    def notes_path(self) -> Path:
        if self.notes_dir.strip():
            return Path(self.notes_dir).expanduser()
        return PROJECT_ROOT / "data" / "notes"

    def sessions_path(self) -> Path:
        if self.sessions_dir.strip():
            return Path(self.sessions_dir).expanduser()
        return PROJECT_ROOT / "data" / "sessions"


def _load_dotenv() -> None:
    if not ENV_PATH.is_file():
        return
    for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def load_config() -> AppConfig:
    _load_dotenv()
    data: dict = {}
    if CONFIG_PATH.is_file():
        try:
            data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            data = {}

    cfg = AppConfig(
        llm_enabled=_env_bool("LLM_ENABLED", data.get("llm_enabled", True)),
        llm_provider=os.environ.get("LLM_PROVIDER", data.get("llm_provider", "lmstudio")),
        llm_base_url=os.environ.get("LLM_BASE_URL", data.get("llm_base_url", "http://127.0.0.1:1234")),
        llm_model=os.environ.get("LLM_MODEL", data.get("llm_model", "google/gemma-4-e4b")),
        llm_max_tokens=int(os.environ.get("LLM_MAX_TOKENS", data.get("llm_max_tokens", 8192))),
        llm_api_key=os.environ.get("LLM_API_KEY", data.get("llm_api_key", "")),
        transcripts_dir=data.get("transcripts_dir", ""),
        notes_dir=data.get("notes_dir", ""),
        aggressive_dedup_default=bool(data.get("aggressive_dedup_default", False)),
        last_transcript=data.get("last_transcript", ""),
        last_output_dir=data.get("last_output_dir", ""),
        whisper_engine=data.get("whisper_engine", "transformers"),
        whisper_model=data.get("whisper_model", "openai/whisper-large-v3-turbo"),
        whisper_device=data.get("whisper_device", "auto"),
        whisper_language=data.get("whisper_language", ""),
        whisper_task=data.get("whisper_task", "transcribe"),
        last_audio_file=data.get("last_audio_file", ""),
        capture_enabled=bool(data.get("capture_enabled", False)),
        capture_auto_interval_sec=float(data.get("capture_auto_interval_sec", 120.0)),
        context_folder=data.get("context_folder", ""),
        refine_second_pass=bool(data.get("refine_second_pass", True)),
        enrich_with_references=bool(data.get("enrich_with_references", True)),
        fast_mode=bool(data.get("fast_mode", False)),
        llm_temperature=float(data.get("llm_temperature", 0.3)),
        last_session=data.get("last_session", ""),
        sessions_dir=data.get("sessions_dir", ""),
        captions_method=data.get("captions_method", "uia"),
        captions_poll_interval=float(data.get("captions_poll_interval", 0.5)),
        captions_duration_sec=float(data.get("captions_duration_sec", 0.0)),
        whisper_live_chunk_sec=float(data.get("whisper_live_chunk_sec", 10.0)),
        whisper_live_source=data.get("whisper_live_source", "system"),
        use_semantic_chunking=bool(data.get("use_semantic_chunking", True)),
        semantic_chunk_threshold=float(data.get("semantic_chunk_threshold", 0.45)),
        use_tag_extraction=bool(data.get("use_tag_extraction", True)),
        inject_wikilinks=bool(data.get("inject_wikilinks", True)),
        semantic_cache_enabled=bool(data.get("semantic_cache_enabled", True)),
        semantic_cache_threshold=float(data.get("semantic_cache_threshold", 0.95)),
        semantic_cache_max_age_days=int(data.get("semantic_cache_max_age_days", 30)),
    )
    return cfg


def save_config(cfg: AppConfig) -> None:
    CONFIG_PATH.write_text(json.dumps(asdict(cfg), indent=2), encoding="utf-8")


def _env_bool(key: str, default: bool) -> bool:
    raw = os.environ.get(key)
    if raw is None:
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")
