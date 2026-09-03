"""Project root paths — use from any module under backend/."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WORDS_PATH = ROOT / "public" / "data" / "words.json"
GREF_MATERIAL_DIR = ROOT / "gref_material" / "gre words"

_db_primary = ROOT / "data" / "vocab_app.db"
_db_legacy = ROOT / "vocab_app.db"
if _db_primary.exists():
    DB_PATH = _db_primary
elif _db_legacy.exists():
    DB_PATH = _db_legacy
else:
    DB_PATH = _db_primary
    _db_primary.parent.mkdir(parents=True, exist_ok=True)
DATA_LOGS_DIR = ROOT / "data_logs"
ASSETS_DIR = ROOT / "assets"
PLATE_IMAGES_DIR = ROOT / "data" / "plate_images"
TRANSCRIPTS_DIR = ROOT / "data" / "transcripts"
QUESTIONS_DIR = ROOT / "data" / "questions"
NOTES_DIR = ROOT / "data" / "notes"
NOTES_RULES_DIRNAME = "rules"
NOTES_RULES_DIR = NOTES_DIR / NOTES_RULES_DIRNAME
SNAPSHOTS_DIR = ROOT / "data" / "transcripts" / "snapshots"
RAW_LIBRARY_DIR = ROOT / "data" / "raw_library"
CORPUS_DIR = ROOT / "data" / "corpus"
LOGS_DIR = ROOT / "data" / "logs"
DOWNLOADS_DIR = ROOT / "data" / "downloads"
LLM_USAGE_DIR = ROOT / "data" / "llm_usage"
LLM_TIERS_PATH = ROOT / "data" / "llm_tiers.json"
LLM_ROUTES_PATH = ROOT / "data" / "llm_routes.json"
