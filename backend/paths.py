"""Project root paths — use from any module under backend/."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WORDS_PATH = ROOT / "public" / "data" / "words.json"

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
