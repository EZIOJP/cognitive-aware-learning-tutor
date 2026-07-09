"""One-off: remove zen.exe rows from tracked_sessions (not a blacklist)."""
import sqlite3
from pathlib import Path

db = Path(__file__).resolve().parents[1] / "data" / "vocab_app.db"
conn = sqlite3.connect(db)
cur = conn.cursor()
cur.execute("SELECT COUNT(1) FROM tracked_sessions WHERE lower(app_name) LIKE '%zen%'")
before = cur.fetchone()[0]
cur.execute("DELETE FROM tracked_sessions WHERE lower(app_name) LIKE '%zen%'")
conn.commit()
print(f"Deleted {cur.rowcount} rows (matched {before})")
