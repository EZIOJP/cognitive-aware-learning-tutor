#!/usr/bin/env python3
"""Export classify_rules.json for calt_enforcer (P5b / Focus standalone Phase 3).

Authoring source remains Python (_APP_RULES / _DOMAIN_RULES / category_scores).
C++ reads the generated file — never a second hardcoded rule list.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from backend.behavior.tracker_classify import _APP_RULES  # noqa: E402
from backend.behavior.domain_classify import _DOMAIN_RULES  # noqa: E402
from backend.behavior.category_scores import PRODUCTIVE_THRESHOLD  # noqa: E402


def main() -> int:
    out = ROOT / "data" / "behavior" / "classify_rules.json"
    out.parent.mkdir(parents=True, exist_ok=True)

    scores: dict[str, int] = {}
    for _, cat, score in list(_APP_RULES) + list(_DOMAIN_RULES):
        scores.setdefault(cat, int(score))

    doc = {
        "schema_version": 1,
        "updated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "default_score": 35,
        "productive_threshold": int(PRODUCTIVE_THRESHOLD),
        "app_rules": [
            {"pattern": p, "category": c, "score": int(s)} for p, c, s in _APP_RULES
        ],
        "domain_rules": [
            {"pattern": p, "category": c, "score": int(s)} for p, c, s in _DOMAIN_RULES
        ],
        "category_scores": {k: int(v) for k, v in sorted(scores.items())},
    }
    out.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {out} ({len(doc['app_rules'])} app + {len(doc['domain_rules'])} domain rules)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
