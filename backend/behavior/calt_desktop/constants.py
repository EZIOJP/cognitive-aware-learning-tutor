"""Shared constants — stack probes only; desktop UI uses native tabs, not these URLs."""

from __future__ import annotations

# Legacy web URLs — used by tracker/browser gate, not CALT Desktop UI.
LOGIN_URL = "http://localhost:5173/login"
CALENDAR_URL = "http://localhost:5173/productivity"
STUDY_URL = "http://localhost:5173/"
HUB_HEALTH_URL = "http://127.0.0.1:8765/health"
