"""Agent debug NDJSON logger (session 4e07c3). Remove after verification."""

from __future__ import annotations

import json
import time
from pathlib import Path

_DEBUG_LOG = Path(__file__).resolve().parents[2] / "debug-4e07c3.log"


def agent_log(*, location: str, message: str, data: dict, hypothesis_id: str) -> None:
    # #region agent log
    entry = {
        "sessionId": "4e07c3",
        "location": location,
        "message": message,
        "data": data,
        "hypothesisId": hypothesis_id,
        "timestamp": int(time.time() * 1000),
    }
    try:
        with _DEBUG_LOG.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry, default=str) + "\n")
    except OSError:
        pass
    # #endregion
