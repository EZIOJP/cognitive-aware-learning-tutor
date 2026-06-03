"""
Compatibility shim — use `backend.main:app` for uvicorn.

  python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
"""

from backend.main import app

__all__ = ["app"]
